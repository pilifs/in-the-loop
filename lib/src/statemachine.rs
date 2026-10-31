//! The state machine a behavioural contract describes, drawn for reviewers.
//!
//! A contract of a method of the shape `decide(State, Input) => Outcome[next=State, ...]` is a transition table.
//! This module reads it back as a graph: states, transitions labelled with their inputs, and the facts a reviewer
//! wants from a state machine: which states are unreachable, which are terminal, and which inputs are refused.

use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;

use crate::contract::Contract;
use crate::Error;

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Transition {
    pub from: String,
    pub to: String,
    pub input: String,
    /// The outcome's text after `next`, such as `effects=[SELL_SEATS]`, for labels.
    pub detail: String,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize)]
pub struct StateMachine {
    pub states: BTreeSet<String>,
    pub transitions: Vec<Transition>,
    /// Inputs that leave the state unchanged, by state: `(state, input, outcome kind)`.
    pub unchanged: Vec<(String, String, String)>,
    /// Inputs that throw, by state.
    pub throws: Vec<(String, String, String)>,
}

/// Reads the machine from a contract. `next_field` names the outcome field holding the next state (`next`).
pub fn from_contract(contract: &Contract, next_field: &str) -> Result<StateMachine, Error> {
    let mut machine = StateMachine::default();
    let needle = format!("{next_field}=");
    for (input, outcome) in &contract.cases {
        let Some(open) = input.find('(') else { continue };
        let Some(close) = input.rfind(')') else { continue };
        let args = &input[open + 1..close];
        let Some((state, rest)) = args.split_once(", ") else { continue };
        if state == "null" || rest == "null" || state.contains('[') {
            continue;
        }
        machine.states.insert(state.to_string());
        if let Some(pos) = outcome.find(&needle) {
            let after = &outcome[pos + needle.len()..];
            let to: String = after.chars().take_while(|c| c.is_alphanumeric() || *c == '_').collect();
            machine.states.insert(to.clone());
            // The rest of the outcome's fields, without the record's closing bracket.
            let mut detail = after[to.len()..].trim_start_matches(", ").to_string();
            if detail.ends_with(']') {
                detail.pop();
            }
            machine.transitions.push(Transition { from: state.to_string(), to, input: rest.to_string(), detail });
        } else if let Some(exception) = outcome.strip_prefix("throws ") {
            machine.throws.push((state.to_string(), rest.to_string(), exception.to_string()));
        } else {
            let kind = outcome.split('[').next().unwrap_or(outcome).to_string();
            machine.unchanged.push((state.to_string(), rest.to_string(), kind));
        }
    }
    if machine.transitions.is_empty() {
        return Err(Error::new(format!("{}: no outcome has a `{next_field}` field; is this a state machine?", contract.target)));
    }
    Ok(machine)
}

impl StateMachine {
    /// States no transition leads to (other than from themselves).
    pub fn unreachable(&self) -> Vec<String> {
        self.states.iter().filter(|s| !self.transitions.iter().any(|t| &t.to == *s && t.from != t.to)).cloned().collect()
    }

    /// States with no transition to another state.
    pub fn terminal(&self) -> Vec<String> {
        self.states.iter().filter(|s| !self.transitions.iter().any(|t| &t.from == *s && t.to != t.from)).cloned().collect()
    }

    /// Transitions grouped by `(from, to)`, with their input labels.
    fn edges(&self) -> BTreeMap<(String, String), Vec<String>> {
        let mut edges: BTreeMap<(String, String), Vec<String>> = BTreeMap::new();
        for t in &self.transitions {
            let label = if t.detail.is_empty() { t.input.clone() } else { format!("{} → {}", t.input, t.detail) };
            edges.entry((t.from.clone(), t.to.clone())).or_default().push(label);
        }
        edges
    }

    /// A Mermaid `stateDiagram-v2`.
    pub fn mermaid(&self) -> String {
        let mut out = String::from("stateDiagram-v2\n");
        let unreachable = self.unreachable();
        let terminal = self.terminal();
        for state in &self.states {
            let mut notes = Vec::new();
            if unreachable.contains(state) {
                notes.push("no incoming transition");
            }
            if terminal.contains(state) {
                notes.push("terminal");
            }
            if !notes.is_empty() {
                out.push_str(&format!("    {state}: {state} ({})\n", notes.join(", ")));
            }
        }
        for ((from, to), labels) in self.edges() {
            for label in labels {
                out.push_str(&format!("    {from} --> {to}: {}\n", label.replace(':', "\\:")));
            }
        }
        for (state, input, kind) in &self.unchanged {
            out.push_str(&format!("    {state} --> {state}: {input} ({kind})\n"));
        }
        out
    }

    /// A Graphviz digraph.
    pub fn dot(&self) -> String {
        let mut out = String::from("digraph contract {\n    rankdir=LR;\n    node [shape=box, fontname=\"Helvetica\"];\n");
        let unreachable = self.unreachable();
        let terminal = self.terminal();
        for state in &self.states {
            let mut attrs = Vec::new();
            if unreachable.contains(state) {
                attrs.push("style=dashed");
            }
            if terminal.contains(state) {
                attrs.push("peripheries=2");
            }
            out.push_str(&format!("    \"{state}\" [{}];\n", attrs.join(", ")));
        }
        for ((from, to), labels) in self.edges() {
            out.push_str(&format!("    \"{from}\" -> \"{to}\" [label=\"{}\"];\n", labels.join("\\n").replace('"', "\\\"")));
        }
        for (state, input, kind) in &self.unchanged {
            out.push_str(&format!("    \"{state}\" -> \"{state}\" [label=\"{input} ({kind})\", style=dotted];\n"));
        }
        out.push_str("}\n");
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_transitions_and_finds_terminal_states() {
        let contract = Contract::new(
            "a.L#decide",
            None,
            vec![
                ("decide(PENDING, Captured[held=true])".into(), "Transition[next=CONFIRMED, effects=[SELL]]".into()),
                ("decide(PENDING, Declined[])".into(), "Transition[next=DECLINED, effects=[]]".into()),
                ("decide(CONFIRMED, Declined[])".into(), "Unchanged[reason=\"x\"]".into()),
                ("decide(DECLINED, Cancel[])".into(), "Rejected[reason=\"y\"]".into()),
                ("decide(null, Cancel[])".into(), "throws NullPointerException".into()),
            ],
        );
        let machine = from_contract(&contract, "next").unwrap();
        assert_eq!(machine.states.len(), 3);
        assert_eq!(machine.transitions.len(), 2);
        assert_eq!(machine.transitions[0].detail, "effects=[SELL]");
        assert_eq!(machine.unreachable(), vec!["PENDING"]);
        assert_eq!(machine.terminal(), vec!["CONFIRMED", "DECLINED"]);
        let mermaid = machine.mermaid();
        assert!(mermaid.contains("PENDING --> CONFIRMED: Captured[held=true] → effects=[SELL]"), "{mermaid}");
        assert!(mermaid.contains("DECLINED --> DECLINED: Cancel[] (Rejected)"), "{mermaid}");
        assert!(machine.dot().contains("\"PENDING\" -> \"CONFIRMED\""));
    }
}
