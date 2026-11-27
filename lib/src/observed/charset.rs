//! An effective charset inside the selected VM, and the calls actually made between entry
//! and normal return of the initialization boundary. Reading the setting after that boundary
//! does not contribute a premise by itself.
use super::{Jvm, Observed, Runtime};
use crate::classfile::{ClassFile, Constant, Insn, MemberRef};
use crate::classpath::ClassPath;
use crate::digest::sha256_hex;
use crate::Error;
use serde_json::{json, Value};
use super::receipt::{read_json, trace};
use std::path::Path;

const DEFAULT: &str = "defaultCharset()Ljava/nio/charset/Charset;";
const BYTES: &str = "getBytes()[B";

#[derive(Clone, Copy, Debug, Eq, PartialEq, serde::Serialize, serde::Deserialize)]
pub enum CharsetLocale {
    #[serde(rename = "C")]
    C,
    #[serde(rename = "C.UTF-8")]
    CUtf8,
}
impl CharsetLocale {
    pub(super) fn name(self) -> &'static str { match self { Self::C => "C", Self::CUtf8 => "C.UTF-8" } }
    pub(crate) fn apply(self, command: &mut std::process::Command) {
        command.env("LC_ALL", self.name()).env("LANG", self.name());
        for option in ["JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"] { command.env_remove(option); }
    }
}

impl Runtime {
    pub(super) fn validate_charset(&self) -> Result<(), String> {
        if self.charset_receipt_directory.is_some() && self.charset_locale.is_none() {
            return Err("charsetReceiptDirectory requires charsetLocale".into());
        }
        if self.charset_locale.is_some() && (self.empty_environment || self.preinitialize_together || self.processors.is_some() || self.root_working_directory || self.reflective_members) {
            return Err("charsetLocale requires a single first-use initializer and its own process profile".into());
        }
        if let Some(id) = &self.expected_charset_receipt {
            if self.charset_locale.is_none() || id.len() != 64 || !id.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()) {
                return Err("expectedCharsetReceipt requires charsetLocale and a lowercase SHA-256".into());
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct Fact {
    pub canonical: String,
    pub id: String,
    pub encoding: Option<(u32, String)>,
    profile: Value,
}

pub(super) fn supported_reference(m: &MemberRef) -> bool {
    matches!((m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()),
        ("java/nio/charset/Charset", "defaultCharset", "()Ljava/nio/charset/Charset;") | ("java/lang/String", "getBytes", "()[B"))
}

/// Admit the small direct computation from the original binary, regardless of its name.
/// The native engine will execute this whole initializer, including its store.
fn literal_encoding(cf: &ClassFile) -> Result<Option<(u32, Vec<u16>, String)>, Error> {
    if cf.super_class.as_deref() != Some("java/lang/Object") || !cf.interfaces.is_empty() { return Ok(None); }
    let Some(code) = cf.method("<clinit>", "()V").and_then(|m| m.code.as_ref()) else { return Ok(None) };
    if !code.exception_table.is_empty() { return Ok(None); }
    let insns = code.instructions()?;
    let [(_, Insn::Ldc(i)), (pc, Insn::InvokeVirtual(m)), (_, Insn::ArrayLength), (_, Insn::PutStatic(f)), (_, Insn::Return(None))] = &insns[..] else { return Ok(None) };
    let Constant::String { string_index } = cf.pool.get(*i)? else { return Ok(None) };
    let method = cf.pool.member(*m)?;
    let field = cf.pool.member(*f)?;
    if method.owner != "java/lang/String" || !supported_reference(&method) || field.owner != cf.name || field.descriptor != "I" { return Ok(None); }
    Ok(Some((*pc, cf.pool.utf16(*string_index)?.into_owned(), field.name)))
}

pub(crate) fn units_digest(units: &[u16]) -> String {
    sha256_hex(&units.iter().flat_map(|u| u.to_be_bytes()).collect::<Vec<_>>())
}

fn encoded(units: &[u16], utf8: bool) -> Vec<u8> {
    let mut bytes = Vec::new();
    for c in char::decode_utf16(units.iter().copied()) {
        match c {
            Ok(c) if utf8 => bytes.extend(c.encode_utf8(&mut [0; 4]).as_bytes()),
            Ok(c) if c.is_ascii() => bytes.push(c as u8),
            _ => bytes.push(b'?'),
        }
    }
    bytes
}

/// Reuse only a trace of a straight-line operation whose full input and sole store
/// are fixed by the selected original bytes. Even here the new subject confirms the
/// effective profile and field. A prior empty trace cannot certify a later absence.
pub(super) fn reusable(work: &Path, tool: &ClassPath, internal: &str, runtime: &Runtime, binding: &Value) -> Result<Option<Value>, Error> {
    let Some(id) = &runtime.expected_charset_receipt else { return Ok(None) };
    let dir = runtime.charset_receipt_directory.clone().unwrap_or_else(|| work.join("startup-receipts"));
    let path = dir.join(format!("{id}.json"));
    if !path.try_exists()? { return Ok(None); }
    let mut receipt = read_json(&path)?;
    let recorded_id = receipt.as_object_mut().and_then(|obj| obj.remove("id"));
    if recorded_id.as_ref().and_then(Value::as_str) != Some(id) || sha256_hex(receipt.to_string().as_bytes()) != *id || receipt["binding"] != *binding {
        return Err(Error::new("startup receipt digest or original runtime binding changed"));
    }
    let Some(class) = tool.application(internal)? else { return Ok(None) };
    Ok(literal_encoding(&class)?.map(|_| receipt))
}

pub(super) fn qualify(binary: &str, line: &str, jvm: &Jvm, tool: &ClassPath, binding: &Value, observed: &Observed, saved: Option<&Value>) -> Result<(Fact, Value), Error> {
    let raw: Value = serde_json::from_str(line).map_err(|e| Error::new(e.to_string()))?;
    let profile = &raw["on"]["charsetProfile"];
    let fresh;
    let events = if let Some(record) = saved { &record["executed"] } else {
        fresh = trace(jvm, binary, "")?;
        &fresh["events"]
    }.as_array().ok_or_else(|| Error::new("missing charset events"))?;
    let canonical = profile["canonical"].as_str().unwrap_or("");
    let implementation = match canonical { "UTF-8" => "sun.nio.cs.UTF_8", "US-ASCII" => "sun.nio.cs.US_ASCII", _ => return Err(Error::new("unsupported effective default charset")) };
    if profile["implementation"] != implementation || profile["standardSingleton"] != true || profile["bootstrap"] != true
        || profile["module"] != "java.base" || profile["locale"] != jvm.runtime.charset_locale.unwrap().name() {
        return Err(Error::new("subject did not confirm the requested locale and a standard bootstrap charset"));
    }
    let internal = binary.replace('.', "/");
    let class = tool.application(&internal)?.ok_or_else(|| Error::new("startup root disappeared"))?;
    let literal = literal_encoding(&class)?;
    let mut encoding = None;
    if !events.is_empty() || literal.is_some() {
        let err = || Error::new(format!("unsupported or incomplete default charset operation in {binary}: {}",
            events.first().and_then(|e| e["stack"].get(1)).unwrap_or(&Value::Null)));
        let (pc, units, field) = literal.ok_or_else(err)?;
        let [selection, bytes] = events.as_slice() else { return Err(err()) };
        let site = format!("{binary}#<clinit>()V@{pc}");
        let expected = encoded(&units, canonical == "UTF-8");
        let digest = units_digest(&units);
        if selection["operation"] != DEFAULT || bytes["operation"] != BYTES || selection["implementation"] != implementation
            || selection["stack"][1] != "java.lang.String#getBytes()[B@0" || selection["stack"][2] != site || bytes["stack"][1] != site
            || selection["canonical"] != canonical || bytes["canonical"] != canonical || bytes["utf16Sha256"] != digest
            || bytes["bytesSha256"] != sha256_hex(&expected) || bytes["length"].as_u64() != Some(expected.len() as u64)
            || observed.fields.get(&field) != Some(&super::Slot::Number(expected.len() as i64)) { return Err(err()); }
        encoding = Some((pc, digest));
    }
    let refs: Vec<_> = class.pool.entries().iter().enumerate().filter_map(|(i, _)| class.pool.member(i as u16).ok())
        .filter(supported_reference).map(|m| format!("{}#{}{}", m.owner, m.name, m.descriptor)).collect();
    let mut receipt = json!({"schema":"jvm-startup-receipt/v1","binding":binding,"root":binary,"rootSha256":observed.on.sha256,
        "rootOrigin":observed.on.from,"jdk":observed.jdk,"vendor":observed.on.vendor,"locale":raw["on"]["locale"],"zone":observed.on.zone,
        "observationBoundary":"first active initialization, before inspecting fields","profile":profile,"potentialReferences":refs,
        "executed":events,"supportedOperation":if encoding.is_some() { "encode the bound original UTF-16 literal" } else { "no default charset call in the recorded initializer" }});
    let id = sha256_hex(receipt.to_string().as_bytes());
    if jvm.runtime.expected_charset_receipt.as_ref().is_some_and(|expected| expected != &id) {
        return Err(Error::new(format!("startup receipt mismatch for {binary}: measured {id}")));
    }
    receipt["id"] = id.clone().into();
    Ok((Fact { canonical: canonical.to_string(), id, encoding, profile: profile.clone() }, receipt))
}

pub(super) fn compare_alone(binary: &str, line: &str, jvm: &Jvm, fact: &Fact) -> Result<(), Error> {
    let state: Value = serde_json::from_str(line).map_err(|e| Error::new(e.to_string()))?;
    if state["charsetProfile"] != fact.profile || !trace(jvm, binary, ".alone")?["events"].as_array().unwrap().is_empty() {
        return Err(Error::new(format!("unqualified charset use or different process profile during comparison of {binary} alone")));
    }
    Ok(())
}

pub(super) fn publish(work: &Path, runtime: &Runtime, receipt: &Value, reused: bool) -> Result<(), Error> {
    let dir = runtime.charset_receipt_directory.clone().unwrap_or_else(|| work.join("startup-receipts"));
    let path = super::receipt::write(&dir, receipt)?;
    eprintln!("startup receipt {}: {} ({})", receipt["id"].as_str().unwrap(),
        if reused { "reused trace, freshly checked subject" } else { "fresh JVM trace" }, path.display());
    Ok(())
}
