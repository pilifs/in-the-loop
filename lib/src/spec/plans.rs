//! The interfaces of `llm-dlc/loops/application-core.md` (its Phase 0 step 2): the types its four streams meet at.
//! They extend the foundations IR beside them ([`super`]), and are no second specification system: a claim carries
//! them in the places it already has, a [`super::Construction::Planned`] domain and a [`super::ModeledCall`]'s
//! [`CallModel`].
//!
//! | Type | Least it means | Produced by, then used by |
//! |---|---|---|
//! | [`ConstructionPlan`] | typed leaves, bounded arrays, constructor or factory makers, shared node identities, the receiver root, an optional short setup sequence, and the domain's explicit restrictions | objects ([`crate::construction`]); then values, environment and reuse |
//! | [`ValueDomain`], [`WitnessValue`] | a value's domain, bounds and evidence, and how a witness holds one to replay it | values ([`crate::values`]); then objects and environment |
//! | [`CallModel`] | a modelled operation's stable id, its argument key, its coupling or occurrence policy, the results or exceptions it permits, and its bound | environment ([`crate::environment`]); then the cache and replay |
//! | [`Summary`] | the pre-state and read footprint a helper's proof needs, its alias facts, domain and bounds, the relation between outcomes, its effects, and the keys of the proofs it depends on | reuse ([`crate::reuse`]); then the checker and claim reporting |
//!
//! Every struct here refuses an unknown field, and every enum an unknown variant, so that what one stream adds is
//! never read as absent by another. The file is the planning session's: a stream asks for a change under its
//! Progress, or makes a purely additive one in a block marked with its name. Until a stream implements its part,
//! its module returns [`super::Unsupported`] naming it, and the claim that needs it is refused.

use serde::{Deserialize, Serialize};

/// How one version's inputs are made: a bounded DAG of objects, its roots, and an optional short setup sequence. Not
/// an arbitrary heap allocator, and not an inference of every reachable state.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConstructionPlan {
    /// The objects made, each once, in an order in which each node's arguments come before it. A node used at two
    /// paths is one object, never two equal copies; no node refers to itself or a later one, so there are no cycles.
    pub nodes: Vec<Node>,
    /// The receiver (`this`) and each parameter, by name, in order.
    pub roots: Vec<Root>,
    /// Calls on the receiver, in order, after it is made and before the target (O3 of the objects stream): a
    /// selected, bounded sequence, never a search over histories. Empty for a constructor-only domain, which is a
    /// different claim.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub setup: Vec<SetupCall>,
    /// What the domain leaves out, in the words a result states: "no subclass of shop.Quote", "states after the
    /// setup call only".
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub restrictions: Vec<String>,
    pub bounds: PlanBounds,
}

/// An object of the plan, made once.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Node {
    /// Its id, unique in the plan and stable across a witness's shrinking.
    pub id: u32,
    /// The application class, as a Java name.
    pub class: String,
    pub maker: Maker,
    /// The maker's arguments, in order.
    pub args: Vec<PlanValue>,
}

/// How a node is made.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind", deny_unknown_fields)]
pub enum Maker {
    /// A constructor of the node's class, by descriptor: `(Lshop/Money;I)V`. One explicitly selected where the class
    /// has several; ambiguity is a named choice, never a guess.
    Constructor { descriptor: String },
    /// A static factory, `owner#name(descriptor)`, whose body is supported (modelled or executable), and whose
    /// dependencies enter the claim.
    Factory { method: String },
}

/// A root of the plan: the receiver or a parameter.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Root {
    /// `this`, or the parameter's name.
    pub name: String,
    pub value: PlanValue,
}

/// A value in a plan.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind", deny_unknown_fields)]
pub enum PlanValue {
    /// A symbolic primitive, named by its path from its root (`q.amount.cents`), of a Java type (`long`).
    Leaf {
        path: String,
        #[serde(rename = "type")]
        ty: String,
    },
    /// A bounded symbolic array of primitive elements, at `path`, of at most `max_length` elements; null only where
    /// `nullable`. Within one version, an array used at two paths is one array; the two versions' copies are apart.
    Array {
        path: String,
        element: String,
        max_length: u32,
        #[serde(default, skip_serializing_if = "std::ops::Not::not")]
        nullable: bool,
    },
    /// A value of an adapter's domain (a String, a list), at `path`.
    Adapted { path: String, domain: ValueDomain },
    /// A dependency of the object, of the class or interface `class` (a Java name): no object the plan makes, but
    /// the claim's environment model, whose stubs stand for its calls.
    Dependency { path: String, class: String },
    /// A node of the plan, by id: the same id at two paths is one object. Null where `nullable`; otherwise, where
    /// `same_as` names earlier nodes of its class, one of them by a choice both versions are given alike.
    Node {
        id: u32,
        #[serde(default, skip_serializing_if = "std::ops::Not::not")]
        nullable: bool,
        #[serde(default, skip_serializing_if = "Vec::is_empty")]
        same_as: Vec<u32>,
    },
}

/// A call of the setup sequence, on the receiver.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SetupCall {
    /// `name(descriptor)`, a method of the receiver's class.
    pub method: String,
    /// Its arguments, symbolic, the same logical inputs in both versions.
    pub args: Vec<PlanValue>,
}

/// The plan's bounds, which are the claim's: a plan beyond one is refused, never truncated.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlanBounds {
    /// Objects the plan makes, all roots together.
    pub nodes: u32,
    /// The longest array a leaf is.
    pub max_array_length: u32,
    /// Calls in the setup sequence.
    pub setup_calls: u32,
}

impl ConstructionPlan {
    /// Why the plan is not a bounded DAG of its own nodes, if it isn't: an id twice, an argument that is the node
    /// itself or a later one (a cycle, or an order that hides one), a root or argument naming no node, a choice of
    /// a node of another class, a root twice, or a bound exceeded. Whether the plan is supported is its stream's
    /// ([`crate::construction`]); this is only its shape.
    pub fn shape_problem(&self) -> Option<String> {
        let mut seen: Vec<(u32, &str)> = Vec::new();
        for node in &self.nodes {
            if seen.iter().any(|(id, _)| *id == node.id) {
                return Some(format!("node {} is made twice", node.id));
            }
            for arg in &node.args {
                if let Some(problem) = self.value_problem(arg, &seen, &format!("node {}", node.id)) {
                    return Some(problem);
                }
            }
            seen.push((node.id, &node.class));
        }
        let mut names = Vec::new();
        for root in &self.roots {
            if names.contains(&&root.name) {
                return Some(format!("the root {} is given twice", root.name));
            }
            names.push(&root.name);
            if let Some(problem) = self.value_problem(&root.value, &seen, &root.name) {
                return Some(problem);
            }
        }
        for call in &self.setup {
            for arg in &call.args {
                if let Some(problem) = self.value_problem(arg, &seen, &format!("the setup call {}", call.method)) {
                    return Some(problem);
                }
            }
        }
        if self.nodes.len() > self.bounds.nodes as usize {
            return Some(format!("the plan makes {} objects, more than its bound of {}", self.nodes.len(), self.bounds.nodes));
        }
        if self.setup.len() > self.bounds.setup_calls as usize {
            return Some(format!("the setup sequence has {} calls, more than its bound of {}", self.setup.len(), self.bounds.setup_calls));
        }
        None
    }

    fn value_problem(&self, value: &PlanValue, made: &[(u32, &str)], at: &str) -> Option<String> {
        match value {
            PlanValue::Node { id, same_as, .. } => {
                let Some((_, class)) = made.iter().find(|(m, _)| m == id) else {
                    return Some(format!("{at} uses node {id}, which no earlier node is: a cycle, or no node at all"));
                };
                for other in same_as {
                    match made.iter().find(|(m, _)| m == other) {
                        None => return Some(format!("{at} may be node {other}, which no earlier node is")),
                        Some((_, c)) if c != class => return Some(format!("{at} may be node {other}, a {c}, which is not of its class {class}")),
                        _ => {}
                    }
                }
                None
            }
            PlanValue::Array { path, max_length, .. } if *max_length > self.bounds.max_array_length => {
                Some(format!("{at}'s array {path} may have {max_length} elements, more than the plan's bound of {}", self.bounds.max_array_length))
            }
            _ => None,
        }
    }
}

/// The domain of a value an adapter makes, compares, snapshots, encodes in a witness and replays: a String or a
/// list, with its bounds and the evidence its model has.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ValueDomain {
    pub kind: ValueKind,
    /// Whether null is among its values, apart from every content.
    pub nullable: bool,
    /// The longest one an input is: an input-domain bound. A cap an output or an intermediate value reaches is a
    /// named unresolved limit, never a truncated value.
    pub max_length: u32,
    pub model: ModelEvidence,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind", deny_unknown_fields)]
pub enum ValueKind {
    /// UTF-16 code units, any of them: surrogates alone, an embedded NUL. Content equality is not identity.
    String,
    /// One bounded immutable-list family (`List.of`, `List.copyOf`), its elements of `element`.
    List { element: ElementKind },
}

/// A list's elements.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind", deny_unknown_fields)]
pub enum ElementKind {
    /// Objects of an application class, made as the construction plan makes one.
    Object { class: String },
    String,
}

/// What a model's behaviour rests on.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ModelEvidence {
    /// The model's identity: its source and the JDK it is of.
    pub source: String,
    pub jdk: String,
    pub level: EvidenceLevel,
    /// What it leaves out, in words.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub leaves_out: Vec<String>,
}

/// How much a model is known to agree with the JVM. Sampled conformance is `tested`, never `proved`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EvidenceLevel {
    Implemented,
    Modelled,
    Tested,
    Trusted,
    Proved,
}

/// A value as a witness holds it, to rebuild on the JVM.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind", deny_unknown_fields)]
pub enum WitnessValue {
    Null,
    /// Its UTF-16 code units, never a Rust string, so that no content is lost or made well-formed.
    String { units: Vec<u16> },
    /// The elements, in order: a node at two indices is one object.
    List { elements: Vec<WitnessValue> },
    /// A node of the witness's construction plan, by id.
    Node { id: u32 },
}

/// How a [`super::ModeledCall`] is modelled beyond a normal return (the environment stream's E1–E3): one declared
/// environment both versions see, never two independent streams of responses.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CallModel {
    /// A stable id of the modelled operation, the same in both versions: what correlates their calls.
    pub id: String,
    /// What a result is a function of, in order: the receiver's identity (`this`) and argument paths (`arg0`,
    /// `arg1.code`).
    pub key: Vec<String>,
    pub coupling: Coupling,
    /// The outcomes it may give.
    pub results: Vec<ModelledResult>,
    /// The most calls of it one trace may make: reaching it is unresolved.
    pub bound: u32,
}

/// How the results of calls with the model are related.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind", deny_unknown_fields)]
pub enum Coupling {
    /// A deterministic read-only query of one declared snapshot: equal keys get equal results, and different keys
    /// independent ones, never by the call's position. Stateless: no read after a write.
    Query,
    /// A declared nondeterministic or fallible operation, under an occurrence policy.
    Choice { policy: Occurrence },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind", deny_unknown_fields)]
pub enum Occurrence {
    /// Each call chooses among the results; corresponding calls of the two versions (same id, key and occurrence
    /// of that key) get the same choice.
    PerCall,
    /// A finite script, by index into the results, in order of calls.
    Script { results: Vec<u32> },
}

/// One outcome a modelled call may give.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind", deny_unknown_fields)]
pub enum ModelledResult {
    Returns { value: Returned },
    /// It throws an exception of `class` (checked or not), with no message or cause: a caller that inspects them
    /// is refused, never given an invented one.
    Throws { class: String },
}

/// What a modelled call returns.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind", deny_unknown_fields)]
pub enum Returned {
    Void,
    /// A symbolic value of a primitive Java type, integral or boolean.
    Primitive {
        #[serde(rename = "type")]
        ty: String,
    },
    /// A DTO made by the shared construction plan's root `result`, null where `nullable`, with a stated identity
    /// policy for repeated responses.
    Object { plan: ConstructionPlan, nullable: bool, identity: Identity },
    /// A value of an adapter's domain.
    Adapted { domain: ValueDomain },
}

/// Whether repeated responses of equal keys are one object or fresh ones: stated, never assumed.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Identity {
    Fresh,
    Stable,
}

/// A helper's proof, as a caller may reuse it (the reuse stream's R2): what it needs of the call site, where it
/// applies, and what it rests on. A caller applies it only where it discharges every condition on the actual
/// pre-call state; otherwise it keeps the helper's body, or is unresolved.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Summary {
    /// The helper, `pkg.Class#name(descriptor)`.
    pub helper: String,
    /// The claim key of the helper's own proof.
    pub proof: String,
    /// The read footprint the proof restricts it to: the receiver's and arguments' paths, `this.rate`, `arg0`.
    pub reads: Vec<String>,
    /// The alias and null facts it needs of them, `this.a != this.b`, `this.rate != null`.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub facts: Vec<String>,
    /// The domain it was proved over, as its result states it, and its bounds.
    pub domain: String,
    pub bounds: super::ClaimBounds,
    pub relation: OutcomeRelation,
    pub effects: Effects,
    /// The claim keys of the proofs it rests on, which never lead back to it.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub depends_on: Vec<String>,
}

/// How the two versions' outcomes of the helper relate.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind", deny_unknown_fields)]
pub enum OutcomeRelation {
    Equal,
    /// A relation over `old.` and `new.` a person stated.
    Stated { holds: String },
}

/// What the helper does beyond its result.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind", deny_unknown_fields)]
pub enum Effects {
    /// It reads its footprint and nothing else: no write, allocation, external call, or exception it makes.
    ReadOnly,
    /// It writes this fixed footprint of primitive fields of the receiver, and nothing else (the optional R4).
    Writes { fields: Vec<String> },
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::de::DeserializeOwned;
    use serde_json::{json, Value};

    /// Parses `value` as `T` and writes it back: the same JSON.
    fn round_trips<T: DeserializeOwned + Serialize>(value: Value) -> T {
        let parsed: T = serde_json::from_value(value.clone()).unwrap_or_else(|e| panic!("{e}: {value}"));
        assert_eq!(serde_json::to_value(&parsed).unwrap(), value);
        parsed
    }

    fn refused<T: DeserializeOwned + std::fmt::Debug>(value: Value, says: &str) {
        let e = serde_json::from_value::<T>(value.clone()).expect_err(&format!("{value} is refused"));
        assert!(e.to_string().contains(says), "{e}");
    }

    fn evidence() -> Value {
        json!({"source": "lib/models/java/lang/String.java", "jdk": "21.0.5", "level": "tested", "leaves_out": ["locale"]})
    }

    /// The kernel's quote, `Quote(Money amount, int quantity)`, with a receiver holding a rate and a setup call.
    fn quote_plan() -> Value {
        json!({
            "nodes": [
                {"id": 0, "class": "shop.Money", "maker": {"kind": "constructor", "descriptor": "(J)V"}, "args": [{"kind": "leaf", "path": "q.amount.cents", "type": "long"}]},
                {"id": 1, "class": "shop.Quote", "maker": {"kind": "constructor", "descriptor": "(Lshop/Money;I)V"}, "args": [{"kind": "node", "id": 0}, {"kind": "leaf", "path": "q.quantity", "type": "int"}]},
                {"id": 2, "class": "shop.Pricing", "maker": {"kind": "factory", "method": "shop.Pricing#of(JLshop/Rates;)Lshop/Pricing;"}, "args": [{"kind": "leaf", "path": "this.rate", "type": "long"}, {"kind": "dependency", "path": "this.rates", "class": "shop.Rates"}]}
            ],
            "roots": [
                {"name": "this", "value": {"kind": "node", "id": 2}},
                {"name": "q", "value": {"kind": "node", "id": 1, "nullable": true}},
                {"name": "counts", "value": {"kind": "array", "path": "counts", "element": "int", "max_length": 4}},
                {"name": "code", "value": {"kind": "adapted", "path": "code", "domain": {"kind": {"kind": "string"}, "nullable": false, "max_length": 8, "model": evidence()}}}
            ],
            "setup": [{"method": "raise(J)V", "args": [{"kind": "leaf", "path": "setup.0.by", "type": "long"}]}],
            "restrictions": ["states after the setup call raise only"],
            "bounds": {"nodes": 3, "max_array_length": 4, "setup_calls": 1}
        })
    }

    #[test]
    fn a_construction_plan_round_trips_and_has_its_shape() {
        let plan: ConstructionPlan = round_trips(quote_plan());
        assert_eq!(plan.shape_problem(), None);
        assert_eq!(plan.roots[1].value, PlanValue::Node { id: 1, nullable: true, same_as: Vec::new() });
    }

    #[test]
    fn a_plan_that_is_no_bounded_dag_is_named() {
        let problem = |change: &dyn Fn(&mut ConstructionPlan)| {
            let mut plan: ConstructionPlan = serde_json::from_value(quote_plan()).unwrap();
            change(&mut plan);
            plan.shape_problem().expect("a problem")
        };
        // A node that is its own argument, or a later node's: a cycle.
        assert!(problem(&|p| p.nodes[0].args.push(PlanValue::Node { id: 0, nullable: false, same_as: Vec::new() })).contains("a cycle"));
        assert!(problem(&|p| p.nodes[0].args.push(PlanValue::Node { id: 1, nullable: false, same_as: Vec::new() })).contains("node 0 uses node 1"));
        assert!(problem(&|p| p.nodes[1].id = 0).contains("node 0 is made twice"));
        assert!(problem(&|p| p.roots.push(p.roots[1].clone())).contains("the root q is given twice"));
        assert!(problem(&|p| p.roots[1].value = PlanValue::Node { id: 1, nullable: false, same_as: vec![0] }).contains("a shop.Money, which is not of its class shop.Quote"));
        assert!(problem(&|p| p.bounds.nodes = 2).contains("3 objects, more than its bound of 2"));
        assert!(problem(&|p| p.bounds.setup_calls = 0).contains("more than its bound of 0"));
        assert!(problem(&|p| p.bounds.max_array_length = 3).contains("counts may have 4 elements"));
    }

    #[test]
    fn an_unknown_field_or_variant_is_refused_in_every_interface() {
        let mut plan = quote_plan();
        plan["nodes"][0]["fields"] = json!({});
        refused::<ConstructionPlan>(plan, "unknown field `fields`");
        let mut plan = quote_plan();
        plan["nodes"][0]["maker"] = json!({"kind": "field-by-field"});
        refused::<ConstructionPlan>(plan, "unknown variant `field-by-field`");
        let mut plan = quote_plan();
        plan["roots"][0]["value"]["kind"] = json!("cycle");
        refused::<ConstructionPlan>(plan, "unknown variant `cycle`");
        refused::<ValueDomain>(json!({"kind": {"kind": "map"}, "nullable": false, "max_length": 2, "model": evidence()}), "unknown variant `map`");
        refused::<ValueDomain>(json!({"kind": {"kind": "string"}, "nullable": false, "max_length": 2, "model": evidence(), "truncate": true}), "unknown field `truncate`");
        refused::<WitnessValue>(json!({"kind": "string", "text": "a"}), "unknown field `text`");
        refused::<CallModel>(json!({"id": "rates", "key": [], "coupling": {"kind": "by-position"}, "results": [], "bound": 1}), "unknown variant `by-position`");
        refused::<CallModel>(json!({"id": "rates", "key": [], "coupling": {"kind": "query"}, "results": [{"kind": "throws", "class": "java.io.IOException", "message": "boom"}], "bound": 1}), "unknown field `message`");
        refused::<Summary>(summary().as_object().unwrap().clone().into_iter().chain([("writes".to_string(), json!([]))]).collect(), "unknown field `writes`");
        refused::<Summary>({ let mut s = summary(); s["effects"] = json!({"kind": "anything"}); s }, "unknown variant `anything`");
    }

    #[test]
    fn values_and_witnesses_round_trip_with_every_code_unit() {
        let list: ValueDomain = round_trips(json!({"kind": {"kind": "list", "element": {"kind": "object", "class": "shop.Line"}}, "nullable": true, "max_length": 3, "model": evidence()}));
        assert_eq!(list.model.level, EvidenceLevel::Tested);
        // An isolated surrogate and an embedded NUL are code units like any other.
        let w: WitnessValue = round_trips(json!({"kind": "list", "elements": [{"kind": "string", "units": [0xD800, 0, 97]}, {"kind": "node", "id": 4}, {"kind": "node", "id": 4}, {"kind": "null"}]}));
        let WitnessValue::List { elements } = w else { panic!() };
        assert_eq!(elements[1], elements[2], "one node at two indices");
    }

    #[test]
    fn a_call_model_round_trips() {
        let rates: CallModel = round_trips(json!({
            "id": "rates.lookup",
            "key": ["this", "arg0"],
            "coupling": {"kind": "query"},
            "results": [{"kind": "returns", "value": {"kind": "primitive", "type": "long"}}, {"kind": "throws", "class": "java.io.IOException"}],
            "bound": 2
        }));
        assert_eq!(rates.coupling, Coupling::Query);
        let mut dto = quote_plan();
        dto["setup"] = json!([]);
        dto.as_object_mut().unwrap().remove("setup");
        let _: CallModel = round_trips(json!({
            "id": "quotes.find",
            "key": ["arg0.code"],
            "coupling": {"kind": "choice", "policy": {"kind": "script", "results": [0, 1, 0]}},
            "results": [{"kind": "returns", "value": {"kind": "object", "plan": dto, "nullable": true, "identity": "fresh"}}, {"kind": "returns", "value": {"kind": "void"}}],
            "bound": 3
        }));
    }

    fn summary() -> Value {
        json!({
            "helper": "shop.Pricing#fee(I)J",
            "proof": "0f3a",
            "reads": ["this.rate", "arg0"],
            "facts": ["this != null"],
            "domain": "this: a Pricing made by its constructor",
            "bounds": {"unwind": 16, "max_array_length": 8},
            "relation": {"kind": "equal"},
            "effects": {"kind": "read-only"},
            "depends_on": ["9be1"]
        })
    }

    #[test]
    fn a_summary_round_trips() {
        let s: Summary = round_trips(summary());
        assert_eq!((s.relation, s.effects), (OutcomeRelation::Equal, Effects::ReadOnly));
    }
}
