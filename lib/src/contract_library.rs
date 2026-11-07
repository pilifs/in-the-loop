//! The contract library (step 3d of `llm-dlc/loops/sound-verdicts.md`): contracts for gaps of the tool's own
//! checker that were checked once and are kept, so that a run under `--gaps advised` applies them without the
//! agent writing them again, and without checking them again.
//!
//! It lives in `lib/models/contracts/`, next to the models, and is built into the binary as they are. A file per
//! JDK class, `java.util.Random.contracts`, holds contracts in the format `--contracts` reads
//! ([`crate::gap_contracts`]), each under its gap's id, which names the JDK it was written for. `checked.json` holds
//! a [`Record`] of each check: the contract's [`digest`](crate::gap_contracts::digest), the JDK it was checked on,
//! and the evidence the check gave (proved, tested or trusted, with the proof and the JVM test).
//!
//! In a run, a gap the agent's `--contracts` file has no contract for takes the library's, if it has one. A
//! contract of the file comes first even when it is refused: an agent whose contract is wrong is told so, rather
//! than having the library's applied in its place. A library contract whose record holds (the same contract, the
//! same JDK, and for a proof the same class file in the JDK image) is applied with the record's evidence, and the
//! verdict says it was checked once. One with no record that holds, as after a JDK upgrade, is checked by the run
//! as the agent's are, with a note, until `jvmcontract gap-contracts --record` records it. A contract written for
//! another JDK is checked on the run's under the run's id: a JDK's method may behave otherwise than another's.
//!
//! `--no-contract-library` turns it off, so that only the agent's contracts close gaps.

use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::bmc::gaps::Gap;
use crate::gap_contracts::{self, Accepted, Block, Record, Refused, Source};
use crate::Error;

/// How a contract of the library names where it was written: `lib/models/contracts/java.util.Random.contracts`.
pub const ORIGIN: &str = "lib/models/contracts/";

/// The library's files, built into the binary. A test checks that this is every `.contracts` file of the
/// directory.
const FILES: &[(&str, &str)] = &[
    ("java.lang.Integer.contracts", include_str!("../models/contracts/java.lang.Integer.contracts")),
    ("java.lang.StringBuilder.contracts", include_str!("../models/contracts/java.lang.StringBuilder.contracts")),
    ("java.util.ArrayList.contracts", include_str!("../models/contracts/java.util.ArrayList.contracts")),
    ("java.util.HashMap.contracts", include_str!("../models/contracts/java.util.HashMap.contracts")),
    ("java.util.HashSet.contracts", include_str!("../models/contracts/java.util.HashSet.contracts")),
    ("java.util.Random.contracts", include_str!("../models/contracts/java.util.Random.contracts")),
];

/// The records of the checks, built into the binary.
const RECORDS: &str = include_str!("../models/contracts/checked.json");

/// The file of records in a library's directory.
pub const RECORDS_FILE: &str = "checked.json";

/// `checked.json`: the records, sorted by id and JDK.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
struct RecordsFile {
    kind: String,
    records: Vec<Record>,
}

/// A contract library: its files, by name, with their text, and the records of their checks.
#[derive(Debug, Clone)]
pub struct Library {
    /// How its contracts name the file they were written in: [`ORIGIN`], or a directory's path.
    pub origin: String,
    pub files: Vec<(String, String)>,
    pub records: Vec<Record>,
}

impl Library {
    /// The library built into the binary.
    pub fn embedded() -> Result<Library, Error> {
        Ok(Library { origin: ORIGIN.into(), files: FILES.iter().map(|(n, t)| (n.to_string(), t.to_string())).collect(), records: read_records(RECORDS, "the built-in contract library's checked.json")? })
    }

    /// The library in a directory: its `.contracts` files, in name order, and its `checked.json` if it has one.
    pub fn from_dir(dir: &Path) -> Result<Library, Error> {
        let mut files = Vec::new();
        for entry in std::fs::read_dir(dir).map_err(|e| Error::new(format!("cannot read the contract library {}: {e}", dir.display())))? {
            let path = entry?.path();
            if path.extension().is_some_and(|e| e == "contracts") {
                let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
                files.push((name, std::fs::read_to_string(&path)?));
            }
        }
        files.sort();
        let records_file = dir.join(RECORDS_FILE);
        let records = if records_file.exists() { read_records(&std::fs::read_to_string(&records_file)?, &records_file.display().to_string())? } else { Vec::new() };
        let mut origin = dir.display().to_string();
        if !origin.ends_with('/') {
            origin.push('/');
        }
        Ok(Library { origin, files, records })
    }

    /// Every contract, with the file it is in.
    pub fn blocks(&self) -> Result<Vec<(String, Block)>, Error> {
        let mut out = Vec::new();
        for (name, text) in &self.files {
            let file = format!("{}{name}", self.origin);
            out.extend(gap_contracts::parse(text, &file)?.into_iter().map(|b| (file.clone(), b)));
        }
        Ok(out)
    }

    /// The record of a check of `block` on the JDK `jdk`, if there is one.
    pub fn record(&self, block: &Block, jdk: Option<&str>) -> Option<&Record> {
        let digest = gap_contracts::digest(block);
        self.records.iter().find(|r| r.contract == digest && Some(r.jdk.as_str()) == jdk)
    }

    /// The library's contracts for the gaps `reached`, on the JDK `jdk`, as sources for
    /// [`gap_contracts::load_sources`]: for each gap, its contract written for `jdk` if it has one, else the first
    /// it has, moved to `jdk`'s id, each with its record on `jdk`, if any.
    pub fn sources(&self, reached: &[&Gap], jdk: Option<&str>) -> Result<Vec<Source>, Error> {
        let blocks = self.blocks()?;
        let mut out = Vec::new();
        for gap in reached {
            let of_gap: Vec<&(String, Block)> = blocks.iter().filter(|(_, b)| gap_contracts::gap_of(&b.id).is_some_and(|(g, _)| g == **gap)).collect();
            let written_for = |b: &Block| gap_contracts::gap_of(&b.id).and_then(|(_, v)| v);
            let Some((file, block)) = of_gap.iter().find(|(_, b)| written_for(b).as_deref() == jdk).or(of_gap.first()).copied() else { continue };
            out.push(on_jdk(file, block, jdk, self.record(block, jdk).cloned()));
        }
        Ok(out)
    }
}

/// A library contract as a source on the JDK `jdk`: under `jdk`'s id when it was written for another.
fn on_jdk(file: &str, block: &Block, jdk: Option<&str>, record: Option<Record>) -> Source {
    let (gap, version) = gap_contracts::gap_of(&block.id).expect("the caller found the contract's gap");
    let moved = gap.kind.of_the_jdk() && jdk.is_some() && version.as_deref() != jdk;
    let id = if moved { gap.id(jdk) } else { block.id.clone() };
    Source { block: Block { id, ..block.clone() }, file: file.to_string(), record, written_for: moved.then(|| block.id.clone()) }
}

fn read_records(text: &str, origin: &str) -> Result<Vec<Record>, Error> {
    let file: RecordsFile = serde_json::from_str(text).map_err(|e| Error::new(format!("{origin}: {e}")))?;
    if file.kind != "gap-contract-records" {
        return Err(Error::new(format!("{origin}: a file of records has `\"kind\": \"gap-contract-records\"`")));
    }
    Ok(file.records)
}

/// What checking a library on this JDK found ([`check`]).
#[derive(Debug, Clone, Serialize)]
pub struct Checked {
    /// The JDK the check ran on.
    pub jdk: Option<String>,
    /// Each contract the check accepted, with its evidence, and whether the library's record of it held before.
    pub accepted: Vec<CheckedContract>,
    /// Each contract the check refused, with why.
    pub refused: Vec<Refused>,
    /// The records file written, under `--record`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recorded: Option<String>,
}

/// A contract the check accepted.
#[derive(Debug, Clone, Serialize)]
pub struct CheckedContract {
    #[serde(flatten)]
    pub contract: Accepted,
    /// The id it was written under, when it was written for another JDK.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub written_for: Option<String>,
    /// Whether the library had a record of it on this JDK that held before the check, and why not otherwise.
    pub record_held: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub record_missing: Option<String>,
}

impl Checked {
    /// Whether the library is fit for runs on this JDK: nothing refused, and every contract recorded.
    pub fn ok(&self) -> bool {
        self.refused.is_empty() && (self.recorded.is_some() || self.accepted.iter().all(|c| c.record_held))
    }

    /// The report, a line per contract.
    pub fn report(&self) -> String {
        let mut out = String::new();
        let jdk = self.jdk.as_deref().unwrap_or("an unknown JDK");
        for c in &self.accepted {
            let a = &c.contract;
            let record = if c.record_held { "its record holds".to_string() } else if self.recorded.is_some() { "recorded now".to_string() } else { format!("no record holds: {}", c.record_missing.as_deref().unwrap_or("none")) };
            let level = crate::equivalence::evidence_words(&crate::bmc::gaps::ContractUse { summary: a.summary.clone(), written_by: a.written_by.clone(), evidence: a.evidence, testing: a.testing.clone(), untested: a.untested.clone(), proof: a.proof.clone(), unproved: a.unproved.clone(), recorded: None, file: a.file.clone(), line: a.line, index: 0 });
            out.push_str(&format!("✓ {} ({}:{}): {level}; {record}\n", a.id, a.file, a.line));
        }
        for r in &self.refused {
            out.push_str(&format!("✗ {} ({}:{}): refused: {}\n", r.id, r.file, r.line, r.reason));
        }
        let n = self.accepted.len() + self.refused.len();
        out.push_str(&format!("{n} contract{} checked on JDK {jdk}: {} accepted ({}), {} refused", if n == 1 { "" } else { "s" }, self.accepted.len(), crate::equivalence::contract_levels(self.accepted.iter().map(|c| c.contract.evidence)), self.refused.len()));
        if let Some(f) = &self.recorded {
            out.push_str(&format!("; records written to {f}"));
        } else {
            let missing = self.accepted.iter().filter(|c| !c.record_held).count();
            if missing > 0 {
                out.push_str(&format!("; {missing} with no record that holds on this JDK, which runs check again: --record keeps the evidence"));
            }
        }
        out.push('\n');
        out
    }
}

/// Checks every contract of a library on this JDK, as a run under `--gaps advised` checks the agent's: each is
/// proved against the JDK's bytecode where it can be, and tested on a real JVM, in `work`. A contract written for
/// another JDK is checked on this one, under this JDK's id. With `record` (a library in `dir`), the evidence of
/// each contract accepted is written to `dir/checked.json`, keeping the records for other JDKs of contracts that
/// are still there, so later runs apply it without checking it again. `dir` none is the built-in library, which
/// is checked without recording.
pub fn check(dir: Option<&Path>, work: &Path, record: bool) -> Result<Checked, Error> {
    let library = match dir {
        Some(d) => Library::from_dir(d)?,
        None if record => return Err(Error::new("--record writes a library's checked.json, so it needs the library's directory (--dir lib/models/contracts)")),
        None => Library::embedded()?,
    };
    let jdk = crate::bmc::gaps::jdk_release();
    let cp = crate::witness::classpath(std::iter::empty::<&Path>())?.with_models(true);
    let blocks = library.blocks()?;
    let mut before = Vec::new();
    let sources: Vec<Source> = blocks
        .iter()
        .map(|(file, block)| {
            let previous = library.record(block, jdk.as_deref());
            before.push(match previous {
                None => Err(format!("it has no record of a check on JDK {}", jdk.as_deref().unwrap_or("unknown"))),
                Some(r) => r.holds_for(block, jdk.as_deref(), &cp),
            });
            on_jdk(file, block, jdk.as_deref(), None)
        })
        .collect();
    let written: Vec<(String, Option<String>, Block)> = sources.iter().map(|s| (s.block.id.clone(), s.written_for.clone(), s.block.clone())).collect();
    std::fs::create_dir_all(work)?;
    let loaded = gap_contracts::load_sources(sources, &cp, jdk.as_deref(), &[], work);
    let mut accepted = Vec::new();
    let mut fresh = Vec::new();
    for a in loaded.accepted {
        let i = written.iter().position(|(id, _, _)| *id == a.id).expect("an accepted contract was one of the library's");
        let (_, written_for, block) = &written[i];
        if let Some(j) = jdk.as_deref() {
            fresh.push(Record::of(&a, block, j));
        }
        accepted.push(CheckedContract { contract: a, written_for: written_for.clone(), record_held: before[i].is_ok(), record_missing: before[i].clone().err() });
    }
    let mut recorded = None;
    if record {
        let dir = dir.expect("--record has a directory");
        // The records of contracts still in the library, on other JDKs, and this check's.
        let digests: std::collections::BTreeSet<String> = blocks.iter().map(|(_, b)| gap_contracts::digest(b)).collect();
        let mut records: Vec<Record> = library.records.into_iter().filter(|r| digests.contains(&r.contract) && Some(r.jdk.as_str()) != jdk.as_deref()).collect();
        records.extend(fresh);
        records.sort_by(|a, b| (&a.id, &a.jdk).cmp(&(&b.id, &b.jdk)));
        let file = dir.join(RECORDS_FILE);
        let text = serde_json::to_string_pretty(&RecordsFile { kind: "gap-contract-records".into(), records }).expect("serializable") + "\n";
        std::fs::write(&file, &text)?;
        recorded = Some(file.display().to_string());
    }
    Ok(Checked { jdk, accepted, refused: loaded.refused, recorded })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_built_in_library_is_every_contracts_file_of_its_directory_and_reads() {
        let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("models/contracts");
        let on_disk = Library::from_dir(&dir).unwrap();
        let built_in = Library::embedded().unwrap();
        assert_eq!(on_disk.files, built_in.files, "FILES in contract_library.rs lists every .contracts file of lib/models/contracts");
        assert_eq!(on_disk.records, built_in.records);
        let blocks = built_in.blocks().unwrap();
        assert!(!blocks.is_empty());
        for (file, b) in &blocks {
            let (gap, version) = gap_contracts::gap_of(&b.id).unwrap_or_else(|| panic!("{file}:{}: {} is a gap's id", b.line, b.id));
            assert!(gap.kind.of_the_jdk() && version.is_some(), "{file}:{}: the library is about JDK calls, each naming its JDK", b.line);
            let class = file.rsplit('/').next().unwrap().trim_end_matches(".contracts");
            assert_eq!(gap.owner.replace('/', "."), class, "{file}:{}: a contract is in its class's file", b.line);
        }
    }

    #[test]
    fn a_record_is_about_one_contract_on_one_jdk() {
        let text = "kind: gap-contracts\n\njdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25.0.4.1\n  call: java.util.ArrayList.<init>(int n)\n  # a comment\n  throws: IllegalArgumentException when n < 0\n\n  modifies: nothing\n  written-by: a test\n";
        let block = &gap_contracts::parse(text, "t").unwrap()[0];
        let same = &gap_contracts::parse(&text.replace("  # a comment\n", "").replace("@jdk-25.0.4.1", "@jdk-26"), "t").unwrap()[0];
        let changed = &gap_contracts::parse(&text.replace("n < 0", "n <= 0"), "t").unwrap()[0];
        assert_eq!(gap_contracts::digest(block), gap_contracts::digest(same), "comments, blank lines and the JDK named don't change a contract's digest");
        assert_ne!(gap_contracts::digest(block), gap_contracts::digest(changed));
        let record = Record { id: block.id.clone(), contract: gap_contracts::digest(block), jdk: "25.0.4.1".into(), by: "jvmcontract test".into(), evidence: gap_contracts::Evidence::Tested, testing: None, untested: None, proof: None, unproved: None };
        let cp = crate::witness::classpath(std::iter::empty::<&Path>()).unwrap();
        assert_eq!(record.holds_for(block, Some("25.0.4.1"), &cp), Ok(()));
        assert!(record.holds_for(changed, Some("25.0.4.1"), &cp).unwrap_err().contains("changed"));
        assert!(record.holds_for(block, Some("26"), &cp).unwrap_err().contains("JDK 25.0.4.1"));
        let proved = Record { proof: Some(gap_contracts::Proof { class: "java.lang.Integer".into(), jdk: "25.0.4.1".into(), digest: "sha256:0000".into(), checker: "c".into(), unwind: 16, paths: 1, seconds: 0.0 }), ..record.clone() };
        assert!(proved.holds_for(block, Some("25.0.4.1"), &cp).unwrap_err().contains("bytecode of java.lang.Integer"), "a proof is about one class file");

        // A library with that contract: the gap takes it, moved to the run's JDK when written for another.
        let library = Library { origin: ORIGIN.into(), files: vec![("java.util.ArrayList.contracts".into(), text.into())], records: vec![record] };
        let (gap, _) = gap_contracts::gap_of(&block.id).unwrap();
        let here = &library.sources(&[&gap], Some("25.0.4.1")).unwrap()[0];
        assert_eq!((here.block.id.as_str(), here.written_for.as_deref(), here.record.is_some()), (block.id.as_str(), None, true));
        assert_eq!(here.file, "lib/models/contracts/java.util.ArrayList.contracts");
        let upgraded = &library.sources(&[&gap], Some("26")).unwrap()[0];
        assert_eq!((upgraded.block.id.as_str(), upgraded.written_for.as_deref(), upgraded.record.is_some()), ("jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-26", Some(block.id.as_str()), false));
    }
}
