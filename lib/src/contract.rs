//! A behavioural contract: for one method, every input and its outcome. It is a text file checked in next to the
//! code, so a pull request that changes behaviour also changes this file, and a reviewer sees each changed case.
//!
//! ```text
//! target: net.example.OrderLifecycle#decide
//! domain: OrderStatus (6) × OrderInput (6) = 36 cases
//!
//! decide(PENDING_PAYMENT, PaymentCaptured[seatsStillHeld=false]) => Transition[next=REFUND_PENDING, effects=[REQUEST_REFUND]]
//! decide(null, null)                                             => throws NullPointerException
//! ```

use std::collections::BTreeMap;
use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::Error;

const ARROW: &str = " => ";

/// Cases are kept in domain order: an insertion-ordered map.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Contract {
    /// `pkg.Class#method`.
    pub target: String,
    /// A description of the domain, such as `OrderStatus (6) × OrderInput (6) = 36 cases`.
    pub domain: Option<String>,
    /// `(input, outcome)` in domain order.
    pub cases: Vec<(String, String)>,
    /// Extra `key: value` lines kept in the header, such as `receiver:` for an instance method.
    #[serde(default)]
    pub extras: BTreeMap<String, String>,
}

/// One difference between a checked-in contract and the code.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "lowercase")]
pub enum Change {
    Changed { input: String, contract: String, actual: String },
    Added { input: String, actual: String },
    Removed { input: String, contract: String },
}

impl Change {
    pub fn input(&self) -> &str {
        match self {
            Change::Changed { input, .. } | Change::Added { input, .. } | Change::Removed { input, .. } => input,
        }
    }

    /// The lines the console report prints for this change, in the format the examples generator parses.
    pub fn render(&self) -> String {
        match self {
            Change::Changed { input, contract, actual } => format!("  {input}\n    contract: {contract}\n    actual:   {actual}"),
            Change::Added { input, actual } => format!("  {input}\n    added:    {actual}"),
            Change::Removed { input, contract } => format!("  {input}\n    removed: this input no longer exists (was {contract})"),
        }
    }
}

impl Contract {
    pub fn new(target: &str, domain: Option<String>, cases: Vec<(String, String)>) -> Contract {
        Contract { target: target.to_string(), domain, cases, extras: BTreeMap::new() }
    }

    /// The file name for a target: `OrderLifecycle.decide.contract` for `pkg.OrderLifecycle#decide`, and
    /// `Arithmetic.pow-int-int.contract` for the overload `pkg.Arithmetic#pow(int, int)`.
    pub fn file_name(target: &str) -> String {
        let (class, method) = target.trim().split_once('#').unwrap_or((target.trim(), ""));
        let simple = class.rsplit('.').next().unwrap_or(class);
        let (name, params) = method.split_once('(').unwrap_or((method, ""));
        let params: Vec<String> = params
            .trim_end_matches(')')
            .split(',')
            .map(|p| p.split_whitespace().collect::<String>())
            .filter(|p| !p.is_empty())
            .map(|p| p.rsplit('.').next().unwrap_or(&p).to_string())
            .collect();
        if params.is_empty() {
            format!("{simple}.{}.contract", name.trim())
        } else {
            format!("{simple}.{}-{}.contract", name.trim(), params.join("-"))
        }
    }

    pub fn outcome(&self, input: &str) -> Option<&str> {
        self.cases.iter().find(|(i, _)| i == input).map(|(_, o)| o.as_str())
    }

    pub fn parse(text: &str, origin: &str) -> Result<Contract, Error> {
        let mut target = None;
        let mut domain = None;
        let mut cases = Vec::new();
        let mut extras = BTreeMap::new();
        for line in text.lines() {
            if line.trim().is_empty() || line.starts_with('#') {
                continue;
            }
            if let Some(rest) = line.strip_prefix("target: ") {
                target = Some(rest.trim().to_string());
            } else if let Some(rest) = line.strip_prefix("domain: ") {
                domain = Some(rest.trim().to_string());
            } else if let Some(arrow) = line.find(ARROW) {
                cases.push((line[..arrow].trim().to_string(), line[arrow + ARROW.len()..].trim().to_string()));
            } else if let Some(colon) = line.find(": ") {
                if !line[..colon].contains(['(', ' ']) {
                    extras.insert(line[..colon].to_string(), line[colon + 2..].trim().to_string());
                    continue;
                }
                return Err(Error::new(format!("{origin}: not a case: {line}")));
            } else {
                return Err(Error::new(format!("{origin}: not a case: {line}")));
            }
        }
        let target = target.ok_or_else(|| Error::new(format!("{origin} has no target line")))?;
        Ok(Contract { target, domain, cases, extras })
    }

    pub fn read(file: &Path) -> Result<Contract, Error> {
        let text = std::fs::read_to_string(file).map_err(|e| Error::new(format!("cannot read {}: {e}", file.display())))?;
        Contract::parse(&text, &file.display().to_string())
    }

    /// The contract as text, cases aligned on the arrow.
    pub fn render(&self) -> String {
        let width = self.cases.iter().map(|(i, _)| i.chars().count()).max().unwrap_or(0);
        let mut lines = vec![
            "# Behavioural contract, generated by jvmcontract. Do not edit: regenerate it with `jvmcontract update`.".to_string(),
            "# It lists the outcome of every possible input, and the build checks it against the bytecode.".to_string(),
            "# A change here is a change in what the code does: review it like an API change.".to_string(),
            format!("target: {}", self.target),
        ];
        if let Some(domain) = &self.domain {
            lines.push(format!("domain: {domain}"));
        }
        for (key, value) in &self.extras {
            lines.push(format!("{key}: {value}"));
        }
        lines.push(String::new());
        for (input, outcome) in &self.cases {
            let pad = " ".repeat(width - input.chars().count());
            lines.push(format!("{input}{pad}{ARROW}{outcome}"));
        }
        let mut text = lines.join("\n");
        text.push('\n');
        text
    }

    pub fn write(&self, file: &Path) -> Result<(), Error> {
        if let Some(parent) = file.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(file, self.render())?;
        Ok(())
    }

    /// The changed, added and removed cases between a checked-in contract (`expected`) and the code (`actual`).
    pub fn diff(expected: &Contract, actual: &Contract) -> Vec<Change> {
        let mut out = Vec::new();
        for (input, outcome) in &expected.cases {
            match actual.outcome(input) {
                None => out.push(Change::Removed { input: input.clone(), contract: outcome.clone() }),
                Some(now) if now != outcome => {
                    out.push(Change::Changed { input: input.clone(), contract: outcome.clone(), actual: now.to_string() })
                }
                Some(_) => {}
            }
        }
        for (input, outcome) in &actual.cases {
            if expected.outcome(input).is_none() {
                out.push(Change::Added { input: input.clone(), actual: outcome.clone() });
            }
        }
        out
    }

    /// A unified diff of two renderings, for a reviewer.
    pub fn unified_diff(before: &Contract, after: &Contract, path: &str) -> String {
        unified_diff(&before.render(), &after.render(), &format!("a/{path}"), &format!("b/{path}"))
    }
}

/// A minimal unified diff (full-file hunks, 3 lines of context collapsed into one hunk), without a dependency.
pub fn unified_diff(before: &str, after: &str, before_name: &str, after_name: &str) -> String {
    let a: Vec<&str> = before.lines().collect();
    let b: Vec<&str> = after.lines().collect();
    if a == b {
        return String::new();
    }
    // Longest common subsequence by dynamic programming; contracts are small.
    let (n, m) = (a.len(), b.len());
    let mut table = vec![vec![0u32; m + 1]; n + 1];
    for i in (0..n).rev() {
        for j in (0..m).rev() {
            table[i][j] = if a[i] == b[j] { table[i + 1][j + 1] + 1 } else { table[i + 1][j].max(table[i][j + 1]) };
        }
    }
    let mut ops: Vec<(char, &str)> = Vec::new();
    let (mut i, mut j) = (0, 0);
    while i < n && j < m {
        if a[i] == b[j] {
            ops.push((' ', a[i]));
            i += 1;
            j += 1;
        } else if table[i + 1][j] >= table[i][j + 1] {
            ops.push(('-', a[i]));
            i += 1;
        } else {
            ops.push(('+', b[j]));
            j += 1;
        }
    }
    while i < n {
        ops.push(('-', a[i]));
        i += 1;
    }
    while j < m {
        ops.push(('+', b[j]));
        j += 1;
    }
    // One hunk from the first change to the last, with up to three lines of context either side.
    let first = ops.iter().position(|(c, _)| *c != ' ').unwrap_or(0);
    let last = ops.iter().rposition(|(c, _)| *c != ' ').unwrap_or(ops.len() - 1);
    let start = first.saturating_sub(3);
    let end = (last + 4).min(ops.len());
    let hunk = &ops[start..end];
    let a_start = ops[..start].iter().filter(|(c, _)| *c != '+').count() + 1;
    let b_start = ops[..start].iter().filter(|(c, _)| *c != '-').count() + 1;
    let a_len = hunk.iter().filter(|(c, _)| *c != '+').count();
    let b_len = hunk.iter().filter(|(c, _)| *c != '-').count();
    let mut out = format!("--- {before_name}\n+++ {after_name}\n@@ -{a_start},{a_len} +{b_start},{b_len} @@\n");
    for (c, line) in hunk {
        out.push(*c);
        out.push_str(line);
        out.push('\n');
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trips_through_text() {
        let contract = Contract::new(
            "a.B#f",
            Some("X (2) = 2 cases".into()),
            vec![("f(A)".into(), "1".into()), ("f(LONGER)".into(), "throws E(\"m\")".into())],
        );
        let text = contract.render();
        assert!(text.contains("f(A)      => 1\n"), "{text}");
        let parsed = Contract::parse(&text, "test").unwrap();
        assert_eq!(parsed, contract);
        assert_eq!(Contract::file_name("a.b.C#m"), "C.m.contract");
    }

    #[test]
    fn diff_names_changed_added_and_removed_cases() {
        let before = Contract::new("t#f", None, vec![("f(A)".into(), "1".into()), ("f(B)".into(), "2".into())]);
        let after = Contract::new("t#f", None, vec![("f(A)".into(), "1".into()), ("f(B)".into(), "3".into()), ("f(C)".into(), "4".into())]);
        let diff = Contract::diff(&before, &after);
        assert_eq!(diff.len(), 2);
        assert!(diff[0].render().contains("f(B)\n    contract: 2\n    actual:   3"));
        assert!(diff[1].render().contains("f(C)\n    added:    4"));
        assert_eq!(Contract::diff(&after, &before).iter().filter(|c| matches!(c, Change::Removed { .. })).count(), 1);
        let unified = Contract::unified_diff(&before, &after, "x.contract");
        assert!(unified.contains("-f(B) => 2") && unified.contains("+f(B) => 3") && unified.contains("+f(C) => 4"), "{unified}");
    }
}
