//! The `verify-bytecode` skill (`plugins/jvmcontract`) tells an agent which `jvmcontract` commands to run. Every
//! command it names in code, and every option on it, must be one the CLI accepts, so that a renamed or removed option
//! fails here rather than in an agent's run (step 3e of llm-dlc/loops/sound-verdicts.md).

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;
use std::process::Command;

fn help(args: &[&str]) -> String {
    let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).args(args).arg("--help").output().unwrap();
    assert!(out.status.success(), "jvmcontract {args:?} --help failed");
    String::from_utf8(out.stdout).unwrap()
}

/// Each subcommand with the options its `--help` lists.
fn commands() -> BTreeMap<String, BTreeSet<String>> {
    let option = regex::Regex::new(r"--[a-z][a-z0-9-]*").unwrap();
    let top = help(&[]);
    let names: Vec<String> = top
        .lines()
        .skip_while(|l| !l.starts_with("Commands:"))
        .skip(1)
        .take_while(|l| l.starts_with("  "))
        .filter_map(|l| l.split_whitespace().next().map(str::to_string))
        .filter(|n| n != "help")
        .collect();
    assert!(names.len() > 5, "no commands in {top}");
    names
        .into_iter()
        .map(|name| {
            let options = help(&[&name])
                .lines()
                .filter(|l| l.trim_start().starts_with('-'))
                .flat_map(|l| option.find_iter(l).map(|m| m.as_str().to_string()).collect::<Vec<_>>())
                .collect();
            (name, options)
        })
        .collect()
}

/// The code of a Markdown file: each fenced line (a line ending in `\` joined to the next), and each inline span.
fn code(text: &str) -> Vec<String> {
    let mut spans = Vec::new();
    let mut fenced = false;
    let mut pending = String::new();
    for line in text.lines() {
        if line.trim_start().starts_with("```") {
            fenced = !fenced;
            continue;
        }
        if fenced {
            if let Some(start) = line.strip_suffix('\\') {
                pending.push_str(start);
                continue;
            }
            pending.push_str(line);
            let joined = std::mem::take(&mut pending);
            // A placeholder line of a template (`<every jvmcontract command, in order>`) and a comment are prose.
            let trimmed = joined.trim_start();
            if !trimmed.starts_with('<') && !trimmed.starts_with('#') {
                spans.push(joined);
            }
        } else {
            spans.extend(line.split('`').skip(1).step_by(2).map(str::to_string));
        }
    }
    spans
}

#[test]
fn every_jvmcontract_command_the_skill_names_is_one_the_cli_accepts() {
    let commands = commands();
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../plugins/jvmcontract");
    let files = ["skills/verify-bytecode/SKILL.md", "skills/verify-bytecode/reference.md", "skills/verify-bytecode/report-template.md", "README.md"];
    let invocation = regex::Regex::new(r"jvmcontract ([a-z][a-z-]*)").unwrap();
    let option = regex::Regex::new(r"(?:^|[\s\[(|'])(--[a-z][a-z0-9-]*)").unwrap();
    let mut checked = 0;
    let mut problems = Vec::new();
    for file in files {
        let text = std::fs::read_to_string(root.join(file)).unwrap();
        for span in code(&text) {
            // `GAPS="..."`: the options every proof command of the skill takes.
            if let Some(rest) = span.trim_start().strip_prefix("GAPS=") {
                for flag in option.captures_iter(rest).map(|c| c[1].to_string()) {
                    for proof in ["prove", "equivalence"] {
                        checked += 1;
                        if !commands[proof].contains(&flag) {
                            problems.push(format!("{file}: `jvmcontract {proof}` takes no {flag} ($GAPS)"));
                        }
                    }
                }
                continue;
            }
            let starts: Vec<_> = invocation.captures_iter(&span).map(|c| (c.get(0).unwrap().start(), c[1].to_string(), c.get(0).unwrap().end())).collect();
            for (index, (_, name, end)) in starts.iter().enumerate() {
                let Some(options) = commands.get(name) else {
                    problems.push(format!("{file}: no command `jvmcontract {name}`, in `{span}`"));
                    continue;
                };
                let until = starts.get(index + 1).map_or(span.len(), |next| next.0);
                // The options of this invocation stop at a pipe or redirection into another program.
                let segment = &span[*end..until];
                let segment = segment.split(['|', '>']).next().unwrap();
                for flag in option.captures_iter(segment).map(|c| c[1].to_string()) {
                    checked += 1;
                    if !options.contains(&flag) {
                        problems.push(format!("{file}: `jvmcontract {name}` takes no {flag}, in `{span}`"));
                    }
                }
            }
        }
    }
    assert!(problems.is_empty(), "{}", problems.join("\n"));
    // The skill's own loop is among what was checked: the gap mode, the contracts and the library check.
    assert!(checked > 50, "only {checked} options checked");
    for (command, flag) in [("prove", "--gaps"), ("prove", "--max-trust"), ("prove", "--contracts"), ("gap-contracts", "--record")] {
        assert!(commands[command].contains(flag), "jvmcontract {command} has no {flag}");
    }
}
