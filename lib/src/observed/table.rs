//! Exact, unwrapped system Properties on a controlled launch. Table values stay in
//! the process. Bulk membership and callback order are checked against plain Java.
use super::{receipt, Jvm, Observed, Runtime};
use crate::digest::sha256_hex;
use crate::Error;
use serde_json::{json, Value};
use std::path::Path;

pub(super) const SOURCE: &str = include_str!("LiveTableTrace.java");
pub(super) fn validate(runtime: &Runtime) -> Result<(), Error> {
    if !runtime.live_properties && !runtime.startup_properties.is_empty() {
        return Err(Error::new("startupProperties requires liveProperties"));
    }
    if runtime.live_properties && (!runtime.empty_environment || runtime.preinitialize_together || runtime.reflective_members || runtime.charset_locale.is_some()) {
        return Err(Error::new("liveProperties requires an emptyEnvironment and one first-use root"));
    }
    if runtime.startup_properties.iter().any(|(k,v)| k.is_empty() || k.contains(['=', '\0']) || v.contains('\0')) {
        return Err(Error::new("unsupported startup property launch argument"));
    }
    Ok(())
}

fn parse(line: &str) -> Result<Value, Error> { serde_json::from_str(line).map_err(|e| Error::new(e.to_string())) }

fn checked_events(snapshot: &Value, trace: Value) -> Result<Value, Error> {
    if snapshot["type"] != "java.util.Properties" || !snapshot["count"].is_u64() ||
        ["orderSha256","entriesSha256"].iter().any(|k| snapshot[k].as_str().is_none_or(|s| s.len() != 64)) {
        return Err(Error::new("incomplete ordinary live table projection"));
    }
    let events = trace["events"].as_array().ok_or_else(|| Error::new("missing live table operations"))?;
    let end = events.last().ok_or_else(|| Error::new("missing table boundary"))?;
    if end["operation"] != "table boundary" || end["type"] != snapshot["type"] || end.get("defaults") != Some(&Value::Null)
        || end["newRetainedReferences"] != 0 || end["projection"] != *snapshot { return Err(Error::new("live table shape, inheritance or identity changed")); }
    for event in &events[..events.len()-1] {
        let good = match event["operation"].as_str() {
            Some("forEach(Ljava/util/function/BiConsumer;)V") => ["count","orderSha256","entriesSha256"].iter().all(|k| event[k] == snapshot[k]),
            Some("hashCode()I") => event["hashCode"] == snapshot["hashCode"],
            Some(s) if ["getProperty(", "get(", "containsKey(", "getOrDefault("].iter().any(|prefix| s.starts_with(prefix)) =>
                event["present"].is_boolean() && event["keySha256"].as_str().is_some_and(|k| k.len() == 64) && event.get("resultProjection").is_some(),
            _ => false,
        };
        if !good { return Err(Error::new(format!("live table consumer disagrees with ordinary original projection at {}", event["caller"]))); }
    }
    Ok(trace["events"].clone())
}

pub(super) fn qualify(jvm: &Jvm, name: &str, log: Option<&Path>, line: &str, binding: &Value, observed: &Observed) -> Result<Value, Error> {
    let raw = parse(line)?;
    let snapshot = &raw["on"]["liveTable"];
    let events = checked_events(snapshot, receipt::trace(jvm, name, "")?)?;
    let ordinary = parse(&jvm.run(name, log, false)?)?;
    if ordinary != raw { return Err(Error::new("instrumented and ordinary initializer observations or live property projections differ")); }
    let record = json!({"schema":"jvm-startup-table/v1","root":name,"rootSha256":observed.on.sha256,"rootOrigin":observed.on.from,
        "binding":binding,"loader":observed.on.loader,"jdk":observed.jdk, "vendor":observed.on.vendor,"locale":raw["on"]["locale"],"zone":observed.on.zone,
        "table":snapshot,"events":events,"ordinaryInitializerParity":true,"snapshotSha256":observed.state_sha256,
        "supportedOperations":["own string membership","Properties.forEach callback order","Properties.hashCode"],
        "defaults":null,"replaced":false,"mutated":false});
    publish(jvm.dir.parent().unwrap(), record.clone(), false)?;
    Ok(record)
}

pub(super) fn compare_alone(jvm: &Jvm, name: &str, line: &str, record: &Value) -> Result<(), Error> {
    let snapshot = parse(line)?["liveTable"].clone();
    checked_events(&snapshot, receipt::trace(jvm, name, ".alone")?)?;
    if snapshot != record["table"] { return Err(Error::new(format!("different live table when initializing {name} alone"))); }
    Ok(())
}

pub(super) fn publish(work: &Path, mut record: Value, complete: bool) -> Result<String, Error> {
    record["effectCoverage"] = if complete { "all transitive comparisons passed".into() } else { "live table and ordinary parity only".into() };
    let id = sha256_hex(record.to_string().as_bytes());
    record["id"] = id.clone().into();
    let dir = if complete { "startup-receipts" } else { "startup-diagnostics" };
    let path = receipt::write(&work.join(dir), &record)?;
    eprintln!("live table {} {id} ({})", if complete { "receipt" } else { "observation" }, path.display());
    Ok(id)
}
