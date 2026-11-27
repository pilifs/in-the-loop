//! A fixed-offset timezone observed at the first-use boundary on a pinned original JVM.
use super::{receipt, Observed, Runtime};
use crate::Error;
use serde_json::{json, Value};
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct Fact {
    pub id: String,
    pub millis: i32,
}

/// These canonical IDs have no transition history on the qualified tzdb image.
pub(crate) fn offset(name: &str) -> Option<i32> {
    if matches!(name, "UTC" | "Etc/UTC" | "GMT") { return Some(0); }
    let [b'G', b'M', b'T', sign @ (b'+' | b'-'), a, b, b':', c, d] = *name.as_bytes() else { return None };
    if ![a, b, c, d].iter().all(u8::is_ascii_digit) { return None }
    let hours = i32::from(a - b'0') * 10 + i32::from(b - b'0');
    let minutes = i32::from(c - b'0') * 10 + i32::from(d - b'0');
    if hours > 23 || minutes > 59 { return None }
    Some((hours * 60 + minutes) * 60_000 * if sign == b'-' { -1 } else { 1 })
}

pub(super) fn validate(runtime: &Runtime) -> Result<(), Error> {
    if let Some(name) = &runtime.fixed_zone {
        if offset(name).is_none() { return Err(Error::new("fixedZone requires UTC, Etc/UTC, GMT, or a canonical GMT+HH:MM or GMT-HH:MM")); }
        if runtime.reflective_members || runtime.live_properties || runtime.preinitialize_together || runtime.charset_locale.is_some() {
            return Err(Error::new("fixedZone needs its own first-use observation of the selected root"));
        }
    }
    if runtime.expected_zone_receipt.as_ref().is_some_and(|id| runtime.fixed_zone.is_none() ||
            id.len() != 64 || !id.bytes().all(|c| c.is_ascii_hexdigit())) {
        return Err(Error::new("expectedZoneReceipt needs fixedZone and a SHA-256 digest"));
    }
    Ok(())
}

pub(super) fn qualify(name: &str, observed: &Observed, requested: &str, expected: Option<&str>,
                      line: &str, binding: &Value, work: &Path) -> Result<Fact, Error> {
    let raw: Value = serde_json::from_str(line).map_err(|e| Error::new(e.to_string()))?;
    let fixed = &raw["on"]["fixedZone"];
    let millis = offset(requested).ok_or_else(|| Error::new("unqualified timezone ID"))?;
    if observed.on.zone != requested || fixed != &json!({"id":requested,"property":requested,"offset":millis,
            "type":"sun.util.calendar.ZoneInfo","freshClones":true,"fixedRules":true,"noSecurityManager":true}) {
        return Err(Error::new("original JVM did not establish the requested fixed time zone or clone behavior"));
    }
    let mut doc = json!({"schema":"jvm-process-zone/v1","root":name,"binding":binding,"profile":fixed,
        "rootSha256":observed.on.sha256,"startupBoundary":observed.on.startup_boundary,"loader":observed.on.loader,
        "scope":"initial fixed offset, fresh default copies and explicit non-null default replacement"});
    let id = crate::digest::sha256_hex(doc.to_string().as_bytes());
    if expected.is_some_and(|prior| prior != id) { return Err(Error::new("fixed time zone receipt differs from the requested original profile")); }
    doc["id"] = id.clone().into();
    receipt::write(&work.join("startup-receipts"), &doc)?;
    Ok(Fact { id, millis })
}
