//! `--details`: the statement a verdict is about ([`crate::statement`]) and where its time went
//! ([`crate::phases`]), written under the verdict on the console. Both are in `--json` already; this renders the
//! same data for a person, so the default output stays one verdict and its witness.

use std::fmt::Write;

use crate::equivalence::Search;
use crate::statement::Statement;

/// The serde name of a unit enum value (`non-vacuous`, `stated`), as `--json` writes it.
fn name<T: serde::Serialize>(value: &T) -> String {
    serde_json::to_value(value).ok().and_then(|v| v.as_str().map(str::to_string)).unwrap_or_default()
}

fn seconds(s: f64) -> String {
    if s >= 10.0 {
        format!("{s:.1} s")
    } else {
        format!("{s:.2} s")
    }
}

fn thousands(n: u64) -> String {
    let digits = n.to_string();
    let mut out = String::new();
    for (i, c) in digits.chars().enumerate() {
        if i > 0 && (digits.len() - i) % 3 == 0 {
            out.push(',');
        }
        out.push(c);
    }
    out
}

/// The lines `--details` adds under a verdict; empty when there is nothing to say (no statement, no search).
pub fn render(stated: Option<&Statement>, search: Option<&Search>) -> String {
    let mut out = String::new();
    if let Some(s) = stated {
        let _ = writeln!(out, "  statement ({}):", s.kind);
        let _ = writeln!(out, "    domain: {}", s.domain.text);
        if s.assumptions.is_empty() {
            let _ = writeln!(out, "    assumes: nothing");
        } else {
            let _ = writeln!(out, "    assumes:");
            for a in &s.assumptions {
                let id = a.id.as_deref().map(|i| format!(" {i}")).unwrap_or_default();
                let _ = writeln!(out, "      [{}] {}{id}: {}", name(&a.basis), name(&a.kind), a.text);
            }
        }
        let arrays = if s.observations.arrays.is_empty() { String::new() } else { format!("; arrays after the call: {}", s.observations.arrays.join(", ")) };
        let _ = writeln!(out, "    observes: {}; {}{arrays}", s.observations.result, s.observations.exceptions);
        let mut bounds = Vec::new();
        if let Some(u) = s.bounds.unwind {
            bounds.push(format!("loops unwound {u} times"));
        }
        if let Some(n) = s.bounds.max_array_length {
            bounds.push(format!("arrays of length ≤ {n}"));
        }
        bounds.push(if s.bounds.complete { "search complete within them".into() } else { "search not complete".into() });
        let _ = writeln!(out, "    bounds: {}", bounds.join(", "));
        let models = if s.models.used {
            let digest = s.models.digest.as_deref().map(|d| format!(", {}…", &d[..d.len().min(19)])).unwrap_or_default();
            format!("jvmcontract's models ({} classes{digest})", s.models.classes)
        } else {
            "none".into()
        };
        let jdk = s.models.jdk.as_deref().map(|j| format!("; JDK {j}")).unwrap_or_default();
        let _ = writeln!(out, "    models: {models}{jdk}");
        let solver = s.checker.solver.as_deref().map(|v| format!(", solver {v}")).unwrap_or_default();
        let gaps = s.gap_mode.as_ref().map(|g| format!(", gaps {}", name(g))).unwrap_or_default();
        let _ = writeln!(out, "    checker: {}{solver}{gaps}", s.checker.name);
        if let Some(why) = &s.checker.fallback {
            let _ = writeln!(out, "    fallback: {why}");
        }
        if let Some(c) = &s.confirmation {
            let reason = search.and_then(|s| s.confirmation.as_ref()).and_then(|c| c.reason.as_deref()).map(|r| format!(": {r}")).unwrap_or_default();
            let _ = writeln!(out, "    confirmation: {}{reason}", name(c));
        }
        if let Some(v) = &s.vacuity {
            let _ = writeln!(out, "    vacuity: {} ({}): {}", name(&v.status), name(&v.basis), v.text);
        }
    }
    if let Some(search) = search {
        let total = search.phases.as_ref().map_or(search.seconds, |c| c.seconds);
        let _ = writeln!(out, "  time: {} in all, the verdict by {}", seconds(total), search.checker);
        if let Some(check) = &search.phases {
            let steps = [("checker runs", check.runs), ("setup", check.setup), ("harness", check.harness), ("gaps", check.gaps), ("contracts", check.contracts), ("replay", check.replay), ("jvm", check.jvm), ("other", check.other)];
            let parts: Vec<String> = steps.iter().filter(|(_, s)| *s >= 0.0005).map(|(n, s)| format!("{n} {}", seconds(*s))).collect();
            let _ = writeln!(out, "    driver: {}", parts.join(", "));
        }
        for run in &search.runs {
            let stage = run.stage.as_deref().map(|s| format!(" {s}")).unwrap_or_default();
            let _ = write!(out, "    {} {}{stage}: {}, {}", run.checker, run.purpose, seconds(run.seconds), run.ended);
            if let Some(p) = &run.profile.phases {
                let mut named: Vec<(&str, f64)> = p.named().into_iter().filter(|(_, s)| *s >= 0.0005).collect();
                named.sort_by(|a, b| b.1.total_cmp(&a.1));
                let total: f64 = named.iter().map(|(_, s)| s).sum();
                let shares: Vec<String> = named.iter().map(|(n, s)| if total > 0.0 { format!("{n} {:.0}%", 100.0 * s / total) } else { n.to_string() }).collect();
                let _ = write!(out, "; {}", shares.join(", "));
            }
            let f = &run.profile.formula;
            if let (Some(v), Some(c)) = (f.variables, f.clauses) {
                let _ = write!(out, "; {} variables, {} clauses", thousands(v), thousands(c));
            }
            let _ = writeln!(out);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn thousands_are_grouped() {
        assert_eq!(thousands(7), "7");
        assert_eq!(thousands(240000), "240,000");
        assert_eq!(thousands(3280000), "3,280,000");
    }

    #[test]
    fn nothing_to_say_is_empty() {
        assert_eq!(render(None, None), "");
    }
}
