//! A concrete JVM-property value can propose primitive inputs for an unresolved
//! claim. Only a failed run of the untouched property harness on a fresh JVM
//! qualifies an input. A proof on the restricted prestate is always discarded.

use crate::bmc::gaps::GapSetting;
use crate::classfile::bytecode::{Insn, Kind};
use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};
use crate::classfile::{flags, Type};
use crate::classpath::ClassPath;
use crate::harness;
use crate::jbmc::JbmcResult;
use crate::jvm_witness::{self, Check, DirectCall};
use crate::witness::Replayed;
use crate::Error;
use crate::Verdict;
use std::path::{Path, PathBuf};
use std::time::Duration;

pub(super) struct Trial {
    pub candidate: JbmcResult,
    pub confirmed: Option<(Replayed, String)>,
    pub note: String,
}

/// The refusal identifies a physical initializer. Resolve its key in the
/// selected original bytes. Ambiguous, indirect and nonliteral keys stay open.
fn key(cp: &ClassPath, result: &JbmcResult) -> Option<String> {
    let [gap] = result.gaps.as_slice() else {
        return None;
    };
    if !gap.id.starts_with(
        "jdk-static-method:java.lang.System.getProperty(Ljava/lang/String;)Ljava/lang/String;@",
    ) {
        return None;
    }
    let [site] = gap.sites.as_slice() else {
        return None;
    };
    let site = site
        .rsplit_once(':')
        .filter(|(_, n)| n.parse::<u16>().is_ok())
        .map_or(site.as_str(), |(site, _)| site);
    let owner = site.strip_suffix(".<clinit>")?.replace('.', "/");
    let cf = cp.bytecode(&owner).ok()??;
    let code = cf
        .method("<clinit>", "()V")?
        .code
        .as_ref()?
        .instructions()
        .ok()?;
    let mut keys = std::collections::BTreeSet::new();
    for pair in code.windows(2) {
        if let [(_, Insn::Ldc(literal)), (_, Insn::InvokeStatic(method))] = pair {
            let member = cf.pool.member(*method).ok()?;
            if (
                member.owner.as_str(),
                member.name.as_str(),
                member.descriptor.as_str(),
            ) == (
                "java/lang/System",
                "getProperty",
                "(Ljava/lang/String;)Ljava/lang/String;",
            ) {
                let value = cf.pool.loadable(*literal).ok()?;
                keys.insert(String::from_utf16(&value.string_units()?).ok()?);
            }
        }
    }
    (keys.len() == 1)
        .then(|| keys.pop_first().unwrap())
        .filter(|s| !s.is_empty())
}

fn wrapper(class: &str, key: &str, types: &[Type]) -> Vec<u8> {
    let mut writer = ClassWriter::new(class);
    writer.major = 52;
    let mut code = CodeBuilder::new();
    code.max_locals = types.iter().map(Type::slots).sum();
    code.max_stack = code.max_locals.max(2);
    code.ldc(writer.pool.string(key));
    // A short nonempty value is merely an input-search heuristic. The fresh
    // original JVM below receives no such setting.
    code.ldc(writer.pool.string("_"));
    code.op_u16(
        0xb8,
        writer.pool.method_ref(
            "java/lang/System",
            "setProperty",
            "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;",
        ),
    );
    code.op(0x57);
    let mut slot = 0;
    let mut descriptor = String::from("(");
    for ty in types {
        let kind = match ty {
            Type::Float => Kind::Float,
            Type::Double => Kind::Double,
            Type::Long => Kind::Long,
            _ => Kind::Int,
        };
        code.load(kind, slot);
        descriptor.push_str(&ty.descriptor());
        slot += ty.slots();
    }
    descriptor.push_str(")V");
    code.op_u16(
        0xb8,
        writer
            .pool
            .method_ref(harness::PROPERTY_CLASS, harness::METHOD, &descriptor),
    );
    code.return_(None);
    writer.methods.push(MethodWriter {
        access: flags::PUBLIC | flags::STATIC,
        name: harness::METHOD.into(),
        descriptor,
        code: Some(code),
    });
    writer.to_bytes()
}

#[allow(clippy::too_many_arguments)]
pub(super) fn find(
    cp: &ClassPath,
    original: &JbmcResult,
    entries: &[PathBuf],
    real_entries: &[PathBuf],
    types: &[Type],
    slots: &[u16],
    direct: DirectCall,
    settings: &GapSetting,
    parameters: &crate::bmc::Parameters,
    options: &super::Options,
    budget: Duration,
    work: &Path,
) -> Result<Option<Trial>, Error> {
    if original.verdict != Verdict::Unverifiable
        || budget < Duration::from_secs(1)
        || types.iter().any(|ty| !ty.is_primitive())
    {
        return Ok(None);
    }
    let Some(key) = key(cp, original) else {
        return Ok(None);
    };
    let class = "PropertyPrestateWitness";
    if cp.exists(class) {
        return Ok(None);
    }
    let trial = tempfile::Builder::new()
        .prefix("prestate-")
        .tempdir_in(work)?;
    std::fs::write(
        trial.path().join(format!("{class}.class")),
        wrapper(class, &key, types),
    )?;
    let probe_cp: Vec<_> = std::iter::once(trial.path().to_owned())
        .chain(entries.iter().cloned())
        .collect();
    let candidate = crate::bmc::run_for_proof(
        &probe_cp,
        options.models,
        class,
        harness::METHOD,
        options.unwind,
        options.max_array_length,
        budget,
        settings,
        parameters,
        trial.path(),
    )?;
    let mut candidate = candidate;
    let log = work.join("bmc-startup-witness.log");
    std::fs::copy(&candidate.log, &log)?;
    candidate.log = log;
    let mut confirmed = None;
    let mut note =
        format!("Native startup witness search used U+005F for {key:?} to propose an input.");
    if candidate.verdict == Verdict::Violation {
        let arguments = candidate.arguments(types)?;
        // The replay JVM receives neither the disposable class path nor its property assignment.
        let replay = jvm_witness::run(
            &trial.path().join("ordinary-replay"),
            harness::PROPERTY_CLASS,
            types,
            slots,
            &arguments,
            &[direct],
            real_entries,
        );
        match replay {
            Ok(run) if run.check == Check::Refuted => {
                if let Some(call) = run
                    .calls
                    .into_iter()
                    .next()
                    .filter(|c| c.thrown.is_none() && c.returned.is_some())
                {
                    note.push_str(&format!(" The unchanged property harness failed on a fresh JDK {} with ordinary startup.", run.jdk));
                    confirmed = Some((call, run.jdk));
                } else {
                    note.push_str(
                        " The original public call did not return an observable primitive value.",
                    );
                }
            }
            Ok(run) => note.push_str(&format!(
                " The unchanged property harness on JDK {} reported {:?}.",
                run.jdk, run.check
            )),
            Err(reason) => note.push_str(&format!(
                " The unchanged property harness could not be replayed because {reason}."
            )),
        }
    } else {
        note.push_str(&format!(
            " The restricted native run reported {:?}.",
            candidate.verdict
        ));
        if let Some(reason) = &candidate.problem {
            note.push(' ');
            note.push_str(reason);
        }
    }
    Ok(Some(Trial {
        candidate,
        confirmed,
        note,
    }))
}
