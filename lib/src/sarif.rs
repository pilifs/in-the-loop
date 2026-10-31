//! Findings as SARIF 2.1.0, which GitHub code scanning and SonarQube (`sonar.sarifReportPaths`) both import.

use std::path::Path;

use serde::Serialize;

use crate::Error;

/// One finding: a rule id, a message, and where in the source it is anchored.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Finding {
    pub rule_id: String,
    pub message: String,
    /// A repo-relative path with `/` separators, or `None` when the source was not found.
    pub uri: Option<String>,
    pub line: u32,
}

impl Finding {
    pub fn new(rule_id: &str, message: impl Into<String>, uri: Option<String>, line: u32) -> Finding {
        Finding { rule_id: rule_id.to_string(), message: message.into(), uri, line }
    }
}

/// The rules the tool reports.
pub const RULES: &[(&str, &str)] = &[
    ("behaviour-changed", "The code no longer matches its behavioural contract."),
    ("unverifiable", "The method cannot be verified: it is not pure, or its inputs are not finite."),
    ("capability-changed", "The module's bytecode reaches a capability, or a library, that its contract does not list."),
    ("api-changed", "The module's public API differs from its contract."),
    ("invariant-violated", "The model checker found a behaviour of the model that violates an invariant."),
];

#[derive(Serialize)]
struct Document<'a> {
    version: &'static str,
    #[serde(rename = "$schema")]
    schema: &'static str,
    runs: Vec<Run<'a>>,
}

#[derive(Serialize)]
struct Run<'a> {
    tool: Tool,
    results: Vec<ResultEntry<'a>>,
}

#[derive(Serialize)]
struct Tool {
    driver: Driver,
}

#[derive(Serialize)]
struct Driver {
    name: &'static str,
    version: &'static str,
    rules: Vec<Rule>,
}

#[derive(Serialize)]
struct Rule {
    id: &'static str,
    #[serde(rename = "shortDescription")]
    short_description: Text<'static>,
}

#[derive(Serialize)]
struct Text<'a> {
    text: &'a str,
}

#[derive(Serialize)]
struct ResultEntry<'a> {
    #[serde(rename = "ruleId")]
    rule_id: &'a str,
    level: &'static str,
    message: Text<'a>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    locations: Vec<Location<'a>>,
}

#[derive(Serialize)]
struct Location<'a> {
    #[serde(rename = "physicalLocation")]
    physical_location: PhysicalLocation<'a>,
}

#[derive(Serialize)]
struct PhysicalLocation<'a> {
    #[serde(rename = "artifactLocation")]
    artifact_location: ArtifactLocation<'a>,
    region: Region,
}

#[derive(Serialize)]
struct ArtifactLocation<'a> {
    uri: &'a str,
}

#[derive(Serialize)]
struct Region {
    #[serde(rename = "startLine")]
    start_line: u32,
}

/// The SARIF document for these findings, as pretty-printed JSON.
pub fn render(findings: &[Finding]) -> String {
    let document = Document {
        version: "2.1.0",
        schema: "https://json.schemastore.org/sarif-2.1.0.json",
        runs: vec![Run {
            tool: Tool {
                driver: Driver {
                    name: "jvmcontract",
                    version: env!("CARGO_PKG_VERSION"),
                    rules: RULES.iter().map(|(id, text)| Rule { id, short_description: Text { text } }).collect(),
                },
            },
            results: findings
                .iter()
                .map(|f| ResultEntry {
                    rule_id: &f.rule_id,
                    level: "error",
                    message: Text { text: &f.message },
                    locations: match &f.uri {
                        None => Vec::new(),
                        Some(uri) => vec![Location {
                            physical_location: PhysicalLocation {
                                artifact_location: ArtifactLocation { uri },
                                region: Region { start_line: f.line.max(1) },
                            },
                        }],
                    },
                })
                .collect(),
        }],
    };
    let mut json = serde_json::to_string_pretty(&document).expect("serializable");
    json.push('\n');
    json
}

/// Writes the SARIF document, creating the parent directory.
pub fn write(file: &Path, findings: &[Finding]) -> Result<(), Error> {
    if let Some(parent) = file.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(file, render(findings))?;
    Ok(())
}

/// A repo-relative URI for a source file: `base`-relative when the file is under `base`, else as given.
pub fn relative_uri(base: &Path, file: &Path) -> String {
    let absolute = std::fs::canonicalize(file).unwrap_or_else(|_| file.to_path_buf());
    let base = std::fs::canonicalize(base).unwrap_or_else(|_| base.to_path_buf());
    let relative = absolute.strip_prefix(&base).unwrap_or(&absolute);
    relative.to_string_lossy().replace('\\', "/")
}

/// Finds the source file of a class under the given source roots: `pkg/Outer.java` for `pkg/Outer$Inner`.
pub fn source_file(class_internal_name: &str, source_roots: &[std::path::PathBuf]) -> Option<std::path::PathBuf> {
    let relative = crate::classfile::source_path_of(class_internal_name);
    source_roots.iter().map(|root| root.join(&relative)).find(|p| p.exists())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renders_findings_with_and_without_locations() {
        let findings = vec![
            Finding::new("behaviour-changed", "Behaviour of X#f differs \"quoted\"\nnext line", Some("src/X.java".into()), 12),
            Finding::new("unverifiable", "no source", None, 0),
        ];
        let json = render(&findings);
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();
        let results = &parsed["runs"][0]["results"];
        assert_eq!(results[0]["ruleId"], "behaviour-changed");
        assert_eq!(results[0]["locations"][0]["physicalLocation"]["region"]["startLine"], 12);
        assert!(results[1].get("locations").is_none());
        assert_eq!(parsed["runs"][0]["tool"]["driver"]["rules"].as_array().unwrap().len(), RULES.len());
    }
}
