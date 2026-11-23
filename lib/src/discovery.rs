//! Discover public one-call receiver producers and candidate observations in the bound application bytes.
use crate::classfile::bytecode::{ArithOp, Insn, Kind};
use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};
use crate::classfile::{flags, ClassFile, Method, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::Error;
use serde_json::{json, Value};
use std::path::Path;
use std::rc::Rc;

fn method(cp: &ClassPath, target: &str) -> Result<(Rc<ClassFile>, Method), Error> {
    let (owner, _) =
        crate::verifier::parse_target(target).ok_or_else(|| Error::new("expected class#method"))?;
    let class = cp
        .application(&owner)?
        .ok_or_else(|| Error::new(format!("missing application class {owner}")))?;
    let member = crate::verifier::select_method(&class, target)
        .map_err(Error::new)?
        .clone();
    Ok((class, member))
}

fn binding(cp: &ClassPath, owner: &str) -> Result<crate::classpath::ClassBinding, Error> {
    cp.bind(owner).map_err(|r| Error::new(r.reason))
}

/// Static inventory. A listed instruction may be unreachable and a protected handler may be inapplicable.
pub fn sites(cp: &ClassPath, target: &str) -> Result<Value, Error> {
    let (class, method) = method(cp, target)?;
    let code = method
        .code
        .as_ref()
        .ok_or_else(|| Error::new("selected method has no Code attribute"))?;
    let mut sites = Vec::new();
    let instructions = code.instructions()?;
    for (ordinal, (pc, insn)) in instructions.iter().enumerate() {
        let kinds: &[&str] = match insn {
            Insn::Arith(ArithOp::Div | ArithOp::Rem, Kind::Int | Kind::Long) => {
                &["division-by-zero"]
            }
            Insn::ArrayLoad(_) | Insn::ArrayStore(_) => match insn {
                Insn::ArrayStore(crate::classfile::bytecode::ArrayKind::Ref) => {
                    &["null", "bounds", "array-store"]
                }
                _ => &["null", "bounds"],
            },
            Insn::ArrayLength
            | Insn::GetField(_)
            | Insn::PutField(_)
            | Insn::InvokeVirtual(_)
            | Insn::InvokeInterface(_)
            | Insn::InvokeSpecial(_)
            | Insn::MonitorEnter
            | Insn::MonitorExit => &["null"],
            Insn::CheckCast(_) => &["cast"],
            Insn::NewArray(_) | Insn::ANewArray(_) | Insn::MultiANewArray(_, _) => {
                &["negative-array-size"]
            }
            Insn::If(..)
            | Insn::IfICmp(..)
            | Insn::IfACmp(..)
            | Insn::IfNull(_)
            | Insn::IfNonNull(_) => &["branch"],
            Insn::AThrow => &["throw", "null"],
            Insn::Return(_) => &["return"],
            Insn::New(i) if class.pool.class_name(*i).ok() == Some("java/lang/AssertionError") => {
                &["assertion-allocation"]
            }
            _ => &[],
        };
        for &kind in kinds {
            let handlers: Vec<_> = code
                .exception_table
                .iter()
                .filter(|h| (*pc >= u32::from(h.start_pc)) && *pc < u32::from(h.end_pc))
                .map(|h| json!({"pc":h.handler_pc,"type":h.catch_type}))
                .collect();
            sites.push(json!({"pc":pc,"ordinal":ordinal,"opcode":code.bytes[*pc as usize],"kind":kind,
                              "line":code.line_at(*pc),"handlers":handlers,
                              "branchTargets":insn.targets(),"followingPc":instructions.get(ordinal+1).map(|(p,_)|p),
                              "selection":if kind == "null" && matches!(insn,Insn::AThrow | Insn::InvokeSpecial(_) | Insn::InvokeVirtual(_) | Insn::InvokeInterface(_)) {
                                  "unavailable: distinguish a null receiver from a nested or explicit throw"
                              } else if method.name.starts_with('<') { "unavailable: initializer projection" } else { "supported" }}));
        }
    }
    Ok(
        json!({"binding":binding(cp,&class.name)?, "owner":class.name,"method":method.name,
              "descriptor":method.descriptor,"sites":sites}),
    )
}

fn primitive_kind(ty: &Type) -> Kind {
    match ty {
        Type::Long => Kind::Long,
        Type::Double => Kind::Double,
        Type::Float => Kind::Float,
        _ => Kind::Int,
    }
}

fn load_args(code: &mut CodeBuilder, args: &[Type], mut slot: u16) {
    for t in args {
        code.load(primitive_kind(t), slot);
        slot += t.slots();
    }
}

/// Each emitted entry calls exactly one public constructor or static factory, then the caller's
/// observer. Any extra observer parameters are the matching prefix of the producer's actual inputs.
/// The observer owns the property, including its subsequent public calls and its null policy.
pub fn construct(
    cp: &ClassPath,
    receiver: &str,
    observer: &str,
    output: &Path,
    limit: usize,
    null_collaborators: bool,
    fresh_observer_inputs: bool,
) -> Result<Value, Error> {
    let receiver = receiver.replace('.', "/");
    let (host, observe) = method(cp, observer)?;
    let obs = observe
        .parsed_descriptor()
        .map_err(|e| Error::new(e.to_string()))?;
    if host.access & flags::PUBLIC == 0
        || !observe.is_public()
        || !observe.is_static()
        || obs.params.first() != Some(&Type::Object(receiver.clone()))
        || !obs.params[1..].iter().all(Type::is_primitive)
        || obs.ret != Type::Boolean
    {
        return Err(Error::new("observer must be a public static boolean method on a public class, taking the requested receiver first"));
    }
    let mut missing = Vec::new();
    let mut eligible = Vec::new();
    for name in cp.application_class_names()? {
        let Some(cf) = cp.application(&name)? else {
            continue;
        };
        if cf.access & flags::PUBLIC == 0 {
            continue;
        }
        for m in &cf.methods {
            if !m.is_public() || m.is_synthetic() || m.is_bridge() {
                continue;
            }
            let desc = m
                .parsed_descriptor()
                .map_err(|e| Error::new(e.to_string()))?;
            let constructor = m.is_constructor() && cf.name == receiver && !cf.is_abstract();
            let factory = m.is_static()
                && desc
                    .ret
                    .class_name()
                    .is_some_and(|s| cp.is_subtype(s, &receiver));
            if !constructor && !factory {
                continue;
            }
            let signature = format!("{}#{}{}", cf.name, m.name, m.descriptor);
            let reason = if !null_collaborators && !desc.params.iter().all(Type::is_primitive) {
                Some("reference argument needs another producer or an input domain")
            } else if !fresh_observer_inputs
                && !desc
                    .params
                    .iter()
                    .filter(|t| t.is_primitive())
                    .cloned()
                    .collect::<Vec<_>>()
                    .starts_with(&obs.params[1..])
            {
                Some("observer arguments do not match this producer")
            } else {
                None
            };
            if let Some(reason) = reason {
                missing.push(json!({"producer":signature,"reason":reason}));
                continue;
            }
            eligible.push((signature, cf.clone(), m.clone(), desc.params));
        }
    }
    eligible.sort_by(|a, b| a.0.cmp(&b.0));
    let name = format!(
        "ReceiverHistory{}",
        &crate::digest::sha256_hex(
            format!("{receiver}:{observer}:{limit}:{null_collaborators}:{fresh_observer_inputs}")
                .as_bytes()
        )[..16]
    );
    if cp.exists(&name) {
        return Err(Error::new("generated class would shadow an input class"));
    }
    let mut writer = ClassWriter::new(&name);
    writer.major = 52;
    let mut plans = Vec::new();
    for (i, (signature, cf, m, args)) in eligible.into_iter().enumerate() {
        if i >= limit {
            missing.push(json!({"producer":signature,"reason":"producer limit"}));
            continue;
        }
        let mut code = CodeBuilder::new();
        let mut inputs: Vec<_> = args.iter().filter(|t| t.is_primitive()).cloned().collect();
        let producer_slots: u16 = inputs.iter().map(Type::slots).sum();
        if fresh_observer_inputs {
            inputs.extend_from_slice(&obs.params[1..]);
        }
        let total_slots: u16 = inputs.iter().map(Type::slots).sum();
        if total_slots > 255 {
            missing.push(json!({"producer":signature,"reason":"generated method exceeds the JVM argument-slot limit"}));
            continue;
        }
        let slots: u16 = args.iter().map(Type::slots).sum();
        code.max_stack = (slots + 2).max(obs.params.iter().map(Type::slots).sum());
        code.max_locals = total_slots;
        if m.is_constructor() {
            let c = writer.pool.class(&cf.name);
            code.op_u16(0xbb, c);
            code.op(0x59);
        }
        let mut input_slot = 0;
        for ty in &args {
            if ty.is_reference() {
                code.op(0x01);
            } else {
                code.load(primitive_kind(ty), input_slot);
                input_slot += ty.slots();
            }
        }
        let target = if cf.is_interface() {
            writer
                .pool
                .interface_method_ref(&cf.name, &m.name, &m.descriptor)
        } else {
            writer.pool.method_ref(&cf.name, &m.name, &m.descriptor)
        };
        code.op_u16(if m.is_constructor() { 0xb7 } else { 0xb8 }, target);
        load_args(
            &mut code,
            &obs.params[1..],
            if fresh_observer_inputs {
                producer_slots
            } else {
                0
            },
        );
        let check = if host.is_interface() {
            writer
                .pool
                .interface_method_ref(&host.name, &observe.name, &observe.descriptor)
        } else {
            writer
                .pool
                .method_ref(&host.name, &observe.name, &observe.descriptor)
        };
        code.op_u16(0xb8, check);
        code.return_(Some(Kind::Int));
        let descriptor = MethodDescriptor::new(inputs, Type::Boolean).descriptor();
        let entry = format!("history{i}");
        plans.push(json!({"entry":format!("{name}#{entry}"),"descriptor":descriptor,"producer":signature,
                          "binding":binding(cp,&cf.name)?,"parameters":m.parameter_names(&cf.pool), "nullArgumentPositions":args.iter().enumerate().filter_map(|(i,t)|t.is_reference().then_some(i)).collect::<Vec<_>>()}));
        writer.methods.push(MethodWriter {
            access: flags::PUBLIC | flags::STATIC,
            name: entry,
            descriptor,
            code: Some(code),
        });
    }
    let bytes = writer.to_bytes();
    std::fs::create_dir_all(output)?;
    let file = output.join(format!("{name}.class"));
    use std::io::Write;
    let mut staged = tempfile::NamedTempFile::new_in(output)?;
    staged.write_all(&bytes)?;
    if let Err(e) = staged.persist_noclobber(&file) {
        if e.error.kind() != std::io::ErrorKind::AlreadyExists || std::fs::read(&file)? != bytes {
            return Err(Error::new(format!(
                "cannot publish the generated class at {}: {}",
                file.display(),
                e.error
            )));
        }
    }
    Ok(
        json!({"receiver":receiver,"observer":observer,"observerDescriptor":observe.descriptor,"observerBinding":binding(cp,&host.name)?,
              "generatedClass":name,"generatedSha256":crate::digest::sha256_hex(&bytes),"plans":plans,"missed":missing,
              "maxProducers":limit,"nullCollaborators":null_collaborators,"freshObserverInputs":fresh_observer_inputs,"scope":"one public producer with symbolic primitive arguments on the supplied application classpath; subsequent calls are those of the observer"}),
    )
}
