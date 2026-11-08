//! The values stream's module (`llm-dlc/loops/application-core-values.md`): value adapters for bounded Strings and
//! one bounded immutable-list family, used by object construction, by result and field observation, by effect
//! snapshots and by JVM replay. Registered by Phase 0 of `llm-dlc/loops/application-core.md`, so that the stream
//! starts without editing a shared file.
//!
//! **A String** ([`StringAdapter`]) is its UTF-16 code units, any of them, of at most an explicit number: the
//! domain's `max_length`, an input-domain bound and part of the claim. Null is a value of its own, apart from every
//! content, when the domain is nullable. The adapter:
//! - declares the domain and the evidence of the model behind it ([`string_model`]: the own checker's String
//!   semantics, `tested` by sampled JVM conformance, never `proved`);
//! - gives the own checker the bound ([`StringAdapter::bound`], `bmc::Parameters::max_string_length`);
//! - reads a String argument out of the checker's witness ([`StringAdapter::read`]): its code units, null, or the
//!   same object as an earlier argument;
//! - encodes a String the interpreter holds as a witness holds it ([`ValueAdapter::encode`]: a snapshot of a
//!   result, a field or a payload), and rebuilds one on the interpreter for a replay ([`ValueAdapter::rebuild`]).
//!
//! A String longer than the bound is never cut to it: encoding or rebuilding one is refused, naming the bound.
//!
//! **A list** ([`ListAdapter`]) is one of the JDK's immutable lists (`List.of`, `List.copyOf` of one of them) of at
//! most `max_length` elements, each an object of an application class the construction plan makes. The own checker
//! runs the list models' bytecode (`lib/models`, [`crate::models::CHECKER_RUNS`]), so a list has no symbolic
//! representation of its own: a harness makes one as an application would, by `List.of` over objects it made,
//! from choices the checker is free in ([`ListAdapter::choices`], [`ListAdapter::java`]). The adapter:
//! - declares the domain and the evidence of the model behind it ([`list_model`], with a digest of the models'
//!   bytecode, so that a change in them changes the model's identity);
//! - writes the harness's Java that makes the list: a length, and for each element after the first the made object
//!   it is, so that any two elements may be one object ([`ListAdapter::admitted`], [`ListAdapter::java`]);
//! - reads the list out of the checker's witness, its elements as the plan's nodes ([`ListAdapter::read`]);
//! - encodes a list the interpreter holds as a witness holds it, and rebuilds one by the interpreter's own `List.of`
//!   for a replay ([`ValueAdapter::encode`], [`ValueAdapter::rebuild`]), its elements the plan's objects
//!   ([`Nodes`]).
//!
//! A list outside the family (an `ArrayList`), longer than the bound, or with an element the plan didn't make, is
//! refused by each, never cut or copied into the family.
//!
//! **Each modelled operation** has a record of its own in [`OPERATIONS`] ([`OperationEvidence`]): what implements it
//! in each engine, the JDK it was sampled on, the inputs it admits, the exceptions it was seen to throw, what it
//! leaves out and its level (`tested`), with the boundary cases that sample it (`lib/tests/values.rs` runs them on
//! the JVM, in the interpreter and in the own checker, and checks the record's exceptions against them).
//!
//! Until a check takes an adapter's values (its harness declares the parameter, gives the checker the bound or the
//! choices, and rebuilds the witness through the adapter's `read` and [`ValueAdapter::rebuild`]), [`adapter`]
//! refuses, naming the values stream, and every call site keeps refusing the value it would have handled.

use std::collections::BTreeMap;

use crate::classfile::Type;
use crate::interp::{JStr, Machine, Native, Object, Value};
use crate::spec::plans::{ElementKind, EvidenceLevel, ModelEvidence, ValueDomain, ValueKind, WitnessValue};
use crate::spec::{Part, Unsupported};

/// One kind of value a check can make symbolic, compare, snapshot, encode in a witness and rebuild for replay. Each
/// implementation declares its domain: its bounds, and the evidence its model has.
pub trait ValueAdapter {
    /// The domain it makes values of.
    fn domain(&self) -> &ValueDomain;
    /// A concrete value the interpreter holds, as a witness holds it; an object of the construction plan as its
    /// node in `nodes`.
    fn encode(&self, machine: &Machine<'_>, value: Value, nodes: &Nodes) -> Result<WitnessValue, Unsupported>;
    /// The value a witness holds, made on `machine` for a replay; a node as its object in `nodes`.
    fn rebuild(&self, machine: &mut Machine<'_>, witness: &WitnessValue, nodes: &Nodes) -> Result<Value, Unsupported>;
}

/// The objects of a construction plan, by node id, as one version's run (a replay, a snapshot) holds them: how a
/// witness names an object it doesn't hold the content of. A String needs none.
#[derive(Debug, Clone, Default)]
pub struct Nodes {
    by_id: BTreeMap<u32, Value>,
}

impl Nodes {
    pub fn new() -> Nodes {
        Nodes::default()
    }

    /// Node `id` is `object` in this run.
    pub fn insert(&mut self, id: u32, object: Value) {
        self.by_id.insert(id, object);
    }

    pub fn get(&self, id: u32) -> Option<Value> {
        self.by_id.get(&id).copied()
    }

    /// The node `object` is, by identity: the first id it was given.
    pub fn id_of(&self, object: Value) -> Option<u32> {
        let Value::Ref(r) = object else { return None };
        self.by_id.iter().find(|(_, v)| matches!(v, Value::Ref(o) if *o == r)).map(|(id, _)| *id)
    }
}

/// The adapter for values of `ty` (a parameter's, a field's, a result's or a payload's), of at most `max_length`
/// elements or code units, if a check can take it. Asked where a check meets a `String` or a `List`; its refusal
/// is added to the check's.
///
/// Both adapters are built ([`StringAdapter`], [`ListAdapter`]), but no check's harness declares a String or list
/// parameter, makes it from the adapter's bound or choices, or rebuilds its witness yet: that wiring is in the
/// checks' harness and replay (interface requests of the values stream to the objects stream), so the hook still
/// refuses them, rather than let a check say it has an adapter it can't use.
pub fn adapter(ty: &Type, max_length: u32) -> Result<Box<dyn ValueAdapter>, Unsupported> {
    let _ = max_length;
    if matches!(ty, Type::Object(name) if name == STRING) {
        return Err(Unsupported::new(Part::Values, "a java.lang.String in this check: its value adapter is built (values::StringAdapter), and the values stream builds it into the checks once their harness declares a String parameter, passes its bound to the own checker (bmc::Parameters::max_string_length) and rebuilds its witness in the replay (llm-dlc/loops/application-core-values.md)"));
    }
    if matches!(ty, Type::Object(name) if name == LIST) {
        return Err(Unsupported::new(Part::Values, "a java.util.List in this check: its value adapter is built (values::ListAdapter, an immutable list of List.of over the plan's objects), and the values stream builds it into the checks once their harness makes the list from the adapter's choices (ListAdapter::java) and rebuilds its witness in the replay (llm-dlc/loops/application-core-values.md)"));
    }
    Err(Unsupported::new(Part::Values, format!("a value adapter for {}: the values stream builds it (llm-dlc/loops/application-core-values.md)", ty.java_name())))
}

/// Whether `ty` is one the values stream's adapters are for: a String, or a `java.util.List`. Every other type is
/// another stream's or unsupported, and [`adapter`] isn't asked.
pub fn is_adapted(ty: &Type) -> bool {
    matches!(ty, Type::Object(name) if name == STRING || name == LIST)
}

const STRING: &str = "java/lang/String";
const LIST: &str = "java/util/List";

/// The String model's identity, to be bumped whenever its semantics change, so that evidence cached under the old
/// one is not reused (V3 wires it into the claim key): the own checker's `bmc::Engine::string_method` and
/// `bmc::Engine::concatenation`, and the interpreter's `interp::JStr`, which replays.
pub const STRING_MODEL: &str = "jvmcontract String model 1: lib/src/bmc (Engine::string_method, Engine::concatenation), lib/src/interp (JStr)";

/// The JDK whose `java.lang.String` the model was sampled against (`lib/tests/values.rs`, on the JVM).
pub const STRING_MODEL_JDK: &str = "25.0.5";

/// The evidence of the String model: what it is, the JDK it was sampled on, its level (`tested`: sampled JVM
/// conformance and replayed witnesses, not a proof), and what it leaves out.
pub fn string_model() -> ModelEvidence {
    ModelEvidence {
        source: STRING_MODEL.into(),
        jdk: STRING_MODEL_JDK.into(),
        level: EvidenceLevel::Tested,
        leaves_out: vec![
            "every String method but length, isEmpty, charAt, equals and startsWith, and the compiler's concatenation of Strings, chars and constants: each is a named gap".into(),
            "the content of a number or a boolean made into a String (numeric formatting), which has none: asking for it ends the path with no verdict".into(),
            format!("the content of a concatenation that could pass {} code units (bmc::MAX_STRING_CONTENT): a named limit, never a truncated String", crate::bmc::MAX_STRING_CONTENT),
            "hashCode, intern, compareTo, and the identity of a String made at run time beyond its being a fresh object".into(),
        ],
    }
}

/// The adapter for Strings of at most `max_length` code units, null among them when `nullable`.
#[derive(Debug, Clone)]
pub struct StringAdapter {
    domain: ValueDomain,
}

/// A String argument as the own checker's witness holds it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Witnessed {
    /// A String of its own, or null.
    Value(WitnessValue),
    /// The same object as the argument in this earlier slot.
    SameAs(u32),
}

impl StringAdapter {
    pub fn new(max_length: u32, nullable: bool) -> StringAdapter {
        StringAdapter { domain: ValueDomain { kind: ValueKind::String, nullable, max_length, model: string_model() } }
    }

    /// The bound, as the own checker takes it. Whether a String parameter may be null, or one object with another,
    /// is the check's [`crate::bmc::Parameters::nullable`] and [`crate::bmc::Parameters::may_alias`], as for an
    /// array; `nullable` must agree with this domain's.
    pub fn bound(&self, parameters: &mut crate::bmc::Parameters) {
        parameters.max_string_length = Some(self.domain.max_length);
    }

    /// The String argument in `slot` of the own checker's witness (`bmc::Outcome`'s or `jbmc::JbmcResult`'s raw
    /// maps): its code units, null, or the same object as an earlier argument. Refused, never cut or widened,
    /// when it is outside the domain: longer than the bound, null where the domain isn't nullable, or not code
    /// units.
    pub fn read(&self, raw_arrays: &BTreeMap<u32, Option<Vec<String>>>, raw_same: &BTreeMap<u32, u32>, slot: u32) -> Result<Witnessed, Unsupported> {
        if let Some(&first) = raw_same.get(&slot) {
            return Ok(Witnessed::SameAs(first));
        }
        let gap = |what: String| Unsupported::new(Part::Values, format!("the witness's String in slot {slot}: {what}"));
        match raw_arrays.get(&slot) {
            None => Err(gap("the witness has none".into())),
            Some(None) if self.domain.nullable => Ok(Witnessed::Value(WitnessValue::Null)),
            Some(None) => Err(gap("null, outside a domain that isn't nullable".into())),
            Some(Some(raw)) => {
                let units = raw.iter().map(|u| u.parse::<u16>().map_err(|_| gap(format!("{u:?} is not a code unit")))).collect::<Result<Vec<u16>, _>>()?;
                self.within(units.len()).map_err(gap)?;
                Ok(Witnessed::Value(WitnessValue::String { units }))
            }
        }
    }

    fn within(&self, length: usize) -> Result<(), String> {
        if length > self.domain.max_length as usize {
            return Err(format!("{length} code units, beyond the domain's bound of {}: never cut to it", self.domain.max_length));
        }
        Ok(())
    }
}

impl ValueAdapter for StringAdapter {
    fn domain(&self) -> &ValueDomain {
        &self.domain
    }

    fn encode(&self, machine: &Machine<'_>, value: Value, _: &Nodes) -> Result<WitnessValue, Unsupported> {
        let gap = |what: String| Unsupported::new(Part::Values, format!("a String to encode: {what}"));
        match value {
            Value::Null if self.domain.nullable => Ok(WitnessValue::Null),
            Value::Null => Err(gap("null, outside a domain that isn't nullable".into())),
            Value::Ref(_) => {
                let Some(s) = machine.units_of(value) else {
                    return Err(gap("an object that is not a String".into()));
                };
                self.within(s.len()).map_err(gap)?;
                Ok(WitnessValue::String { units: s.into_units() })
            }
            other => Err(gap(format!("{other:?}, not a reference"))),
        }
    }

    fn rebuild(&self, machine: &mut Machine<'_>, witness: &WitnessValue, _: &Nodes) -> Result<Value, Unsupported> {
        let gap = |what: String| Unsupported::new(Part::Values, format!("a String to rebuild: {what}"));
        match witness {
            WitnessValue::Null if self.domain.nullable => Ok(Value::Null),
            WitnessValue::Null => Err(gap("null, outside a domain that isn't nullable".into())),
            WitnessValue::String { units } => {
                self.within(units.len()).map_err(gap)?;
                Ok(machine.new_string(JStr::from_units(units.clone())))
            }
            other => Err(gap(format!("{other:?}, not a String's"))),
        }
    }
}

/// The list model's identity, to be bumped whenever its semantics change outside the models' bytecode (the
/// interpreter's natives, which replay, or how the checker runs the models); [`list_model`] adds the digest of the
/// bytecode itself.
pub const LIST_MODEL: &str = "jvmcontract list model 1: lib/models (java.util.List, java.util.ImmutableCollections and its list classes, run by the own checker and JBMC), lib/src/interp (Machine::immutable_list, which replays)";

/// The JDK whose immutable lists the models were written after and sampled against (`lib/tests/values.rs`,
/// `lib/tests/conformance.rs`, on the JVM).
pub const LIST_MODEL_JDK: &str = "25.0.5";

/// The most elements a list of the family the adapter makes has: `List.of`'s fixed forms. Its array form
/// (`List.of(E...)`) is left out.
pub const MAX_LIST_LENGTH: u32 = 10;

/// The SHA-256 of the list models' bytecode, in class path order: every model of `java.util.List` and
/// `java.util.ImmutableCollections` the own checker runs.
pub fn list_model_digest() -> String {
    let mut bytes = Vec::new();
    for model in crate::models::MODELS.iter().filter(|m| crate::models::CHECKER_RUNS.contains(&m.name) && (m.name == LIST || m.name.starts_with("java/util/ImmutableCollections"))) {
        bytes.extend_from_slice(model.name.as_bytes());
        bytes.push(0);
        bytes.extend_from_slice(&(model.bytes.len() as u64).to_be_bytes());
        bytes.extend_from_slice(model.bytes);
    }
    crate::digest::sha256_hex(&bytes)
}

/// The evidence of the list model: what it is (with its bytecode's digest), the JDK it follows, its level
/// (`tested`: the models are the JDK's lists written out by hand, sampled by JVM conformance and replayed witnesses,
/// not a proof), and what it leaves out.
pub fn list_model() -> ModelEvidence {
    ModelEvidence {
        source: format!("{LIST_MODEL}; models sha256 {}", list_model_digest()),
        jdk: LIST_MODEL_JDK.into(),
        level: EvidenceLevel::Tested,
        leaves_out: vec![
            "every List implementation but the JDK's immutable List12, ListN and its one empty list: a list made otherwise (an ArrayList) is refused as an input, and copyOf of one reaches its JDK calls, named gaps".into(),
            format!("List.of's array form, for more than {MAX_LIST_LENGTH} elements: no harness makes one"),
            "lists of Strings: the shared ElementKind::String has no bound for its elements' code units yet".into(),
            "the models' methods beyond construction, size, isEmpty, get, the iterator and the changes they refuse (contains, indexOf, equals, hashCode and the like): run as their bytecode is written, sampled only by the conformance corpus".into(),
            "the interpreter's getClass of a list of one or two elements, which names ListN where the JVM's is List12".into(),
        ],
    }
}

/// The adapter for immutable lists of at most `max_length` objects of one application class, null among them when
/// `nullable`.
///
/// **The shape a harness makes** (`tests/fixtures/values/values/Lists.java`'s `list`): the harness makes
/// `max_length` objects by the construction plan, `m0` to `m{k-1}`, and the list from int choices the checker is
/// free in ([`ListAdapter::choices`]): whether it is null (where `nullable`), its length `n` (0 to `max_length`),
/// and for each element `i` after the first the made object it is (`m0` to `mi`), so that every pattern of
/// duplicates and aliases among the elements is a choice. Element 0 is `m0`. The list is `List.of` over the first
/// `n` elements: the JDK's own list, the empty one shared, as the application would make it.
#[derive(Debug, Clone)]
pub struct ListAdapter {
    domain: ValueDomain,
    class: String,
}

impl ListAdapter {
    /// A list of objects of `element` (an `ElementKind::Object`'s Java class name), of at most `max_length`. A
    /// list of Strings, or one longer than [`MAX_LIST_LENGTH`], is refused by name.
    pub fn new(element: ElementKind, max_length: u32, nullable: bool) -> Result<ListAdapter, Unsupported> {
        let class = match &element {
            ElementKind::Object { class } => class.clone(),
            ElementKind::String => return Err(Unsupported::new(Part::Values, "a list of Strings: the shared ElementKind::String has no bound for its elements' code units yet, so the adapter can't bound them (an interface request of the values stream, for the merge)")),
        };
        if max_length > MAX_LIST_LENGTH {
            return Err(Unsupported::new(Part::Values, format!("a list of up to {max_length} elements: the adapter makes lists by List.of's fixed forms, of at most {MAX_LIST_LENGTH}, and its array form is outside the family")));
        }
        Ok(ListAdapter { domain: ValueDomain { kind: ValueKind::List { element }, nullable, max_length, model: list_model() }, class })
    }

    /// The elements' class, as the domain names it (`basket.Line`).
    pub fn element_class(&self) -> &str {
        &self.class
    }

    /// The names of the harness's int choices for the list called `name`, in order: `{name}Null` (where
    /// `nullable`), `{name}Length`, then `{name}Pick1` to `{name}Pick{k-1}`.
    pub fn choices(&self, name: &str) -> Vec<String> {
        let mut out = Vec::new();
        if self.domain.nullable {
            out.push(format!("{name}Null"));
        }
        out.push(format!("{name}Length"));
        out.extend((1..self.domain.max_length).map(|i| format!("{name}Pick{i}")));
        out
    }

    /// The Java condition the choices of `name` are admitted under: the length within the bound, each pick an
    /// object made so far, and the null choice 0 or 1. A harness returns before the check where it is false.
    pub fn admitted(&self, name: &str) -> String {
        let mut parts = Vec::new();
        if self.domain.nullable {
            parts.push(format!("({name}Null == 0 || {name}Null == 1)"));
        }
        parts.push(format!("0 <= {name}Length && {name}Length <= {}", self.domain.max_length));
        parts.extend((1..self.domain.max_length).map(|i| format!("0 <= {name}Pick{i} && {name}Pick{i} <= {i}")));
        parts.join(" && ")
    }

    /// Java statements declaring the list `target` (a `java.util.List<{class}>`, with locals `{target}0` and on) and
    /// making it from the choices of `name`, over `made`, the `max_length` objects the harness made by the plan for
    /// this version, whose class is `class` (the version's Java name for the element class:
    /// `before.basket.Line`). Each version makes its own list, from the same choices.
    pub fn java(&self, name: &str, target: &str, class: &str, made: &[String]) -> Result<String, Unsupported> {
        let k = self.domain.max_length as usize;
        if made.len() != k {
            return Err(Unsupported::new(Part::Values, format!("the list {name}: {} objects made, where the adapter picks among {k}", made.len())));
        }
        let mut out = String::new();
        for i in 0..k {
            let mut pick = made[i].clone();
            for j in (0..i).rev() {
                pick = format!("{name}Pick{i} == {j} ? {} : {pick}", made[j]);
            }
            out.push_str(&format!("{class} {target}{i} = {pick};\n"));
        }
        let of = |n: usize| format!("java.util.List.<{class}>of({})", (0..n).map(|i| format!("{target}{i}")).collect::<Vec<_>>().join(", "));
        let mut list = of(k);
        for n in (0..k).rev() {
            list = format!("{name}Length == {n} ? {} : {list}", of(n));
        }
        if self.domain.nullable {
            list = format!("{name}Null == 1 ? null : {list}");
        }
        out.push_str(&format!("java.util.List<{class}> {target} = {list};\n"));
        Ok(out)
    }

    /// The list the checker's witness gives, from the values of its choices (in [`ListAdapter::choices`]' order)
    /// and the nodes of the objects it made (`made`, in order): null, or its elements as nodes, in order, a node at
    /// two indices one object. Refused, never cut, when a choice is outside what [`ListAdapter::admitted`] admits.
    pub fn read(&self, choices: &[i64], made: &[u32]) -> Result<WitnessValue, Unsupported> {
        let gap = |what: String| Unsupported::new(Part::Values, format!("the witness's list: {what}"));
        let k = self.domain.max_length as usize;
        if choices.len() != self.choices("").len() || made.len() != k {
            return Err(gap(format!("{} choices and {} objects made, where the domain has {} and {k}", choices.len(), made.len(), self.choices("").len())));
        }
        let mut rest = choices;
        if self.domain.nullable {
            match rest[0] {
                1 => return Ok(WitnessValue::Null),
                0 => {}
                other => return Err(gap(format!("the null choice {other}, not 0 or 1"))),
            }
            rest = &rest[1..];
        }
        let length = rest[0];
        if !(0..=k as i64).contains(&length) {
            return Err(gap(format!("{length} elements, outside the domain's 0 to {k}: never cut to it")));
        }
        let mut elements = Vec::new();
        for i in 0..length as usize {
            let pick = if i == 0 { 0 } else { rest[i] };
            if !(0..=i as i64).contains(&pick) {
                return Err(gap(format!("element {i} the made object {pick}, outside 0 to {i}")));
            }
            elements.push(WitnessValue::Node { id: made[pick as usize] });
        }
        Ok(WitnessValue::List { elements })
    }

    fn within(&self, length: usize) -> Result<(), String> {
        if length > self.domain.max_length as usize {
            return Err(format!("{length} elements, beyond the domain's bound of {}: never cut to it", self.domain.max_length));
        }
        Ok(())
    }
}

impl ValueAdapter for ListAdapter {
    fn domain(&self) -> &ValueDomain {
        &self.domain
    }

    /// The elements as the plan's nodes, in order. A list outside the family (a mutable one, another class), longer
    /// than the bound, or holding an object `nodes` doesn't name (one the run made) is refused.
    fn encode(&self, machine: &Machine<'_>, value: Value, nodes: &Nodes) -> Result<WitnessValue, Unsupported> {
        let gap = |what: String| Unsupported::new(Part::Values, format!("a list to encode: {what}"));
        let r = match value {
            Value::Null if self.domain.nullable => return Ok(WitnessValue::Null),
            Value::Null => return Err(gap("null, outside a domain that isn't nullable".into())),
            Value::Ref(r) => r,
            other => return Err(gap(format!("{other:?}, not a reference"))),
        };
        let (Some(_), Object::Native(Native::List { elements, mutable: false })) = (machine.immutable_list_kind(r), machine.heap.get(r)) else {
            return Err(gap(format!("a {}, not one of the JDK's immutable lists List.of and List.copyOf make", machine.class_of(r).replace('/', "."))));
        };
        self.within(elements.len()).map_err(gap)?;
        let elements = elements
            .iter()
            .enumerate()
            .map(|(i, e)| match nodes.id_of(*e) {
                Some(id) => Ok(WitnessValue::Node { id }),
                None => Err(gap(format!("element {i} is no object of the construction plan"))),
            })
            .collect::<Result<Vec<_>, _>>()?;
        Ok(WitnessValue::List { elements })
    }

    /// The list made by the interpreter's `List.of` over the nodes' objects: the JDK's class for its length, the one
    /// empty list for none.
    fn rebuild(&self, machine: &mut Machine<'_>, witness: &WitnessValue, nodes: &Nodes) -> Result<Value, Unsupported> {
        let gap = |what: String| Unsupported::new(Part::Values, format!("a list to rebuild: {what}"));
        match witness {
            WitnessValue::Null if self.domain.nullable => Ok(Value::Null),
            WitnessValue::Null => Err(gap("null, outside a domain that isn't nullable".into())),
            WitnessValue::List { elements } => {
                self.within(elements.len()).map_err(gap)?;
                let values = elements
                    .iter()
                    .enumerate()
                    .map(|(i, e)| match e {
                        WitnessValue::Node { id } => nodes.get(*id).ok_or_else(|| gap(format!("element {i} is node {id}, which the run hasn't made"))),
                        other => Err(gap(format!("element {i} is {other:?}, not a node of the plan"))),
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                Ok(machine.immutable_list(values))
            }
            other => Err(gap(format!("{other:?}, not a list's"))),
        }
    }
}

/// Which of the values models an operation belongs to.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum Family {
    /// [`string_model`].
    String,
    /// [`list_model`].
    List,
}

/// The evidence of one modelled operation (V3): what implements it in each engine, the JDK it was sampled on, the
/// inputs it admits, the exceptions it was seen to throw, what it leaves out, and its level. `sampled_by` names the
/// boundary cases of `lib/tests/fixtures/values/values/Operations.java` that sample it; `lib/tests/values.rs` runs
/// each on the JVM, in the interpreter and in the own checker, which must agree, and checks that the exceptions they
/// throw are exactly `throws`. Sampled conformance is `tested`, never `proved`.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct OperationEvidence {
    /// The operation, as the bytecode names it: `owner.name(descriptor)`, or the instruction.
    pub operation: &'static str,
    pub family: Family,
    /// What implements it: in the own checker, in the interpreter (the replay), and for JBMC.
    pub source: &'static str,
    pub admits: &'static str,
    /// The exceptions it was seen to throw on the JVM, by class, each sampled by a case; nothing else is.
    pub throws: &'static [&'static str],
    pub leaves_out: &'static [&'static str],
    pub level: EvidenceLevel,
    /// The methods of `values.Operations` whose cases sample it.
    pub sampled_by: &'static [&'static str],
}

impl OperationEvidence {
    /// The JDK it was sampled on.
    pub fn jdk(&self) -> &'static str {
        match self.family {
            Family::String => STRING_MODEL_JDK,
            Family::List => LIST_MODEL_JDK,
        }
    }

    /// The model it is part of, whose identity a claim's key carries.
    pub fn model(&self) -> ModelEvidence {
        match self.family {
            Family::String => string_model(),
            Family::List => list_model(),
        }
    }
}

const NPE: &str = "java.lang.NullPointerException";
const STRING_SOURCE: &str = "the own checker: bmc::Engine::string_method on the String's content; the interpreter: interp::JStr; JBMC: its own String model, not this one";
const LIST_SOURCE: &str = "the list models' bytecode (lib/models/java/util/List.java, ImmutableCollections.java), run by the own checker and JBMC; the interpreter: interp::ImmutableList";

/// Every operation of the values models, with its evidence. An operation not here is outside the models: a named
/// gap where a check reaches it.
pub const OPERATIONS: &[OperationEvidence] = &[
    OperationEvidence {
        operation: "ldc of a java.lang.String constant",
        family: Family::String,
        source: "the own checker: bmc::Engine's literal, one interned object with its content; the interpreter: interp::Machine's literal",
        admits: "a literal's code units as the class reader decodes them: NUL and well-formed surrogate pairs kept",
        throws: &[],
        leaves_out: &["a literal with an isolated surrogate in its source, which the class reader decodes as U+FFFD (classfile::decode_modified_utf8) for every engine alike: an interface request for the merge"],
        level: EvidenceLevel::Tested,
        sampled_by: &["literalUnit", "literalInterned"],
    },
    OperationEvidence {
        operation: "invokedynamic makeConcatWithConstants (java.lang.invoke.StringConcatFactory)",
        family: Family::String,
        source: "the own checker: bmc::Engine::concatenation; the interpreter: its string concatenation over interp::JStr",
        admits: "Strings, null (as \"null\"), chars and the recipe's constants, in order",
        throws: &[],
        leaves_out: &[
            "the content of a number, a boolean or an object made into a String: the result has none, and asking for it ends the path with no verdict",
            "the content of a result that could pass bmc::MAX_STRING_CONTENT code units: a named limit, never a truncated String",
        ],
        level: EvidenceLevel::Tested,
        sampled_by: &["concatenated", "withChar"],
    },
    OperationEvidence {
        operation: "java.lang.String.length()I",
        family: Family::String,
        source: STRING_SOURCE,
        admits: "a String with content: a parameter up to its bound, a literal, a concatenation within the cap",
        throws: &[NPE],
        leaves_out: &[],
        level: EvidenceLevel::Tested,
        sampled_by: &["length"],
    },
    OperationEvidence {
        operation: "java.lang.String.isEmpty()Z",
        family: Family::String,
        source: STRING_SOURCE,
        admits: "a String with content",
        throws: &[NPE],
        leaves_out: &[],
        level: EvidenceLevel::Tested,
        sampled_by: &["isEmpty"],
    },
    OperationEvidence {
        operation: "java.lang.String.charAt(I)C",
        family: Family::String,
        source: STRING_SOURCE,
        admits: "a String with content and any int index",
        throws: &["java.lang.StringIndexOutOfBoundsException", NPE],
        leaves_out: &["the exception's message"],
        level: EvidenceLevel::Tested,
        sampled_by: &["charAt"],
    },
    OperationEvidence {
        operation: "java.lang.String.equals(Ljava/lang/Object;)Z",
        family: Family::String,
        source: STRING_SOURCE,
        admits: "a String with content, and as the argument the same object, null, an object of another class, or a String with content",
        throws: &[NPE],
        leaves_out: &["a String argument with no content (a number made into a String), which is a named gap"],
        level: EvidenceLevel::Tested,
        sampled_by: &["equalsContent", "equalsItself", "equalsAnotherClass", "equalNotSame"],
    },
    OperationEvidence {
        operation: "java.lang.String.startsWith(Ljava/lang/String;)Z",
        family: Family::String,
        source: STRING_SOURCE,
        admits: "a String with content, and a String with content or null as the prefix",
        throws: &[NPE],
        leaves_out: &["startsWith(String, int)"],
        level: EvidenceLevel::Tested,
        sampled_by: &["startsWith"],
    },
    OperationEvidence {
        operation: "java.util.List.of: its fixed forms, () to (E, E, E, E, E, E, E, E, E, E)",
        family: Family::List,
        source: LIST_SOURCE,
        admits: "0 to 10 elements, any two of which may be one object; the elements are the objects given, never copies",
        throws: &[NPE],
        leaves_out: &[
            "the array form List.of(E...), for more than 10 elements",
            "the identity of a list beyond the pinned JDK's: List.of() is the one empty list, and any other a fresh list, as JDK 25.0.5 makes them",
        ],
        level: EvidenceLevel::Tested,
        sampled_by: &["ofWithNull", "ofKeepsDuplicates", "elementsAreTheObjects", "emptyIsShared", "otherwiseFresh"],
    },
    OperationEvidence {
        operation: "java.util.List.copyOf(Ljava/util/Collection;)Ljava/util/List;",
        family: Family::List,
        source: LIST_SOURCE,
        admits: "a list of the family, which it returns itself, or null",
        throws: &[NPE],
        leaves_out: &["every other Collection: copyOf of one (an ArrayList) reaches its JDK calls, named gaps"],
        level: EvidenceLevel::Tested,
        sampled_by: &["copyOfIsTheList"],
    },
    OperationEvidence {
        operation: "java.util.List.size()I",
        family: Family::List,
        source: LIST_SOURCE,
        admits: "a list of the family",
        throws: &[],
        leaves_out: &[],
        level: EvidenceLevel::Tested,
        sampled_by: &["size"],
    },
    OperationEvidence {
        operation: "java.util.List.isEmpty()Z",
        family: Family::List,
        source: LIST_SOURCE,
        admits: "a list of the family",
        throws: &[],
        leaves_out: &[],
        level: EvidenceLevel::Tested,
        sampled_by: &["isEmptyList"],
    },
    OperationEvidence {
        operation: "java.util.List.get(I)Ljava/lang/Object;",
        family: Family::List,
        source: LIST_SOURCE,
        admits: "a list of the family and any int index",
        throws: &["java.lang.IndexOutOfBoundsException", "java.lang.ArrayIndexOutOfBoundsException"],
        leaves_out: &["the exception's message", "the interpreter's getClass of a list of one or two, which names ListN (the replay's, not the checker's)"],
        level: EvidenceLevel::Tested,
        sampled_by: &["get"],
    },
    OperationEvidence {
        operation: "java.util.List.iterator()Ljava/util/Iterator; with Iterator.hasNext()Z and next()Ljava/lang/Object;",
        family: Family::List,
        source: LIST_SOURCE,
        admits: "a list of the family: the enhanced for's path",
        throws: &["java.util.NoSuchElementException"],
        leaves_out: &["listIterator, forEach and the other ways of walking a list"],
        level: EvidenceLevel::Tested,
        sampled_by: &["iterated", "nextPastTheEnd"],
    },
    OperationEvidence {
        operation: "java.util.List's changes: add(Ljava/lang/Object;)Z, set(ILjava/lang/Object;)Ljava/lang/Object;, remove(I)Ljava/lang/Object;, clear()V, Iterator.remove()V",
        family: Family::List,
        source: LIST_SOURCE,
        admits: "a list of the family, empty included: each change is refused",
        throws: &["java.lang.UnsupportedOperationException"],
        leaves_out: &["the other changes (addAll, removeIf, sort and the like), which the models refuse as written but no case samples"],
        level: EvidenceLevel::Tested,
        sampled_by: &["add", "set", "removeAt", "clear", "iteratorRemove"],
    },
];

#[cfg(test)]
mod tests {
    use super::*;
    use crate::classpath::ClassPath;

    #[test]
    fn each_operation_has_one_record_of_its_family_tested_never_proved_and_serialized_with_its_cases() {
        let mut names: Vec<&str> = OPERATIONS.iter().map(|r| r.operation).collect();
        names.sort();
        names.dedup();
        assert_eq!(names.len(), OPERATIONS.len(), "one record per operation");
        for record in OPERATIONS {
            assert_eq!(record.level, EvidenceLevel::Tested, "{}", record.operation);
            assert_eq!(record.model().jdk, record.jdk());
            let json = serde_json::to_value(record).unwrap();
            assert_eq!(json["level"], "tested");
            assert!(json["sampled_by"].as_array().is_some_and(|c| !c.is_empty()), "{}", record.operation);
        }
        assert_eq!(OPERATIONS.iter().filter(|r| r.family == Family::String).count(), 7);
        assert!(OPERATIONS.iter().any(|r| r.family == Family::List && r.throws.contains(&"java.lang.ArrayIndexOutOfBoundsException")));
    }

    #[test]
    fn a_string_and_a_list_are_refused_by_name_until_a_check_takes_one() {
        for name in ["java/lang/String", "java/util/List"] {
            let ty = Type::Object(name.into());
            assert!(is_adapted(&ty));
            let gap = adapter(&ty, 8).err().expect("no check takes one yet");
            assert_eq!(gap.part, Part::Values);
            assert!(gap.what.contains("the values stream builds it"), "{gap}");
        }
        let list = adapter(&Type::Object(LIST.into()), 8).err().unwrap();
        assert!(list.what.contains("values::ListAdapter") && list.what.contains("ListAdapter::java"), "{list}");
        let string = adapter(&Type::Object(STRING.into()), 8).err().unwrap();
        assert!(string.what.contains("values::StringAdapter") && string.what.contains("max_string_length"), "{string}");
        assert!(!is_adapted(&Type::Int) && !is_adapted(&Type::Object("shop/Quote".into())));
    }

    #[test]
    fn a_strings_domain_states_its_bound_and_its_models_evidence() {
        let a = StringAdapter::new(5, true);
        let d = a.domain();
        assert_eq!((d.kind.clone(), d.nullable, d.max_length), (ValueKind::String, true, 5));
        assert_eq!(d.model.level, EvidenceLevel::Tested, "sampled conformance is tested, never proved");
        assert_eq!(d.model.jdk, STRING_MODEL_JDK);
        assert!(d.model.leaves_out.iter().any(|l| l.contains("MAX_STRING_CONTENT")));
        let mut p = crate::bmc::Parameters::default();
        a.bound(&mut p);
        assert_eq!(p.max_string_length, Some(5));
        // The domain is the shared type, and writes back the same.
        let json = serde_json::to_value(d).unwrap();
        assert_eq!(serde_json::from_value::<ValueDomain>(json).unwrap(), *d);
    }

    fn raw(units: &[u16]) -> Option<Vec<String>> {
        Some(units.iter().map(u16::to_string).collect())
    }

    #[test]
    fn a_witnessed_string_is_its_code_units_null_or_an_earlier_argument_and_never_cut() {
        let a = StringAdapter::new(3, true);
        let arrays = BTreeMap::from([(0, raw(&[0xD800, 0, 0xDE00])), (1, None), (3, raw(&[1, 2, 3, 4])), (4, Some(vec!["65536".into()]))]);
        let same = BTreeMap::from([(2, 0)]);
        assert_eq!(a.read(&arrays, &same, 0).unwrap(), Witnessed::Value(WitnessValue::String { units: vec![0xD800, 0, 0xDE00] }));
        assert_eq!(a.read(&arrays, &same, 1).unwrap(), Witnessed::Value(WitnessValue::Null));
        assert_eq!(a.read(&arrays, &same, 2).unwrap(), Witnessed::SameAs(0));
        let long = a.read(&arrays, &same, 3).unwrap_err();
        assert!(long.what.contains("4 code units, beyond the domain's bound of 3"), "{long}");
        assert!(a.read(&arrays, &same, 4).unwrap_err().what.contains("not a code unit"));
        assert!(a.read(&arrays, &same, 5).unwrap_err().what.contains("has none"));
        let strict = StringAdapter::new(3, false);
        assert!(strict.read(&arrays, &same, 1).unwrap_err().what.contains("isn't nullable"));
    }

    #[test]
    fn a_string_rebuilt_on_the_interpreter_encodes_as_the_same_code_units_and_nothing_longer_is_cut() {
        let cp = ClassPath::new().with_default_jdk();
        let mut m = Machine::new(&cp);
        let a = StringAdapter::new(4, true);
        let none = Nodes::new();
        for units in [vec![], vec![0], vec![0xD83D, 0xDE00], vec![0xDC00, 0xD800, 0xFFFF, 0x41]] {
            let w = WitnessValue::String { units: units.clone() };
            let v = a.rebuild(&mut m, &w, &none).unwrap();
            assert_eq!(m.units_of(v).unwrap().units(), &units[..]);
            assert_eq!(a.encode(&m, v, &none).unwrap(), w);
        }
        assert_eq!(a.rebuild(&mut m, &WitnessValue::Null, &none).unwrap(), Value::Null);
        assert_eq!(a.encode(&m, Value::Null, &none).unwrap(), WitnessValue::Null);
        let five = WitnessValue::String { units: vec![1; 5] };
        assert!(a.rebuild(&mut m, &five, &none).unwrap_err().what.contains("beyond the domain's bound of 4"));
        let long = m.new_string(JStr::from_units(vec![1; 5]));
        assert!(a.encode(&m, long, &none).unwrap_err().what.contains("never cut"));
        assert!(a.encode(&m, Value::Int(3), &none).is_err());
        assert!(a.rebuild(&mut m, &WitnessValue::Node { id: 1 }, &none).is_err());
        let strict = StringAdapter::new(4, false);
        assert!(strict.encode(&m, Value::Null, &none).is_err() && strict.rebuild(&mut m, &WitnessValue::Null, &none).is_err());
    }

    fn line() -> ElementKind {
        ElementKind::Object { class: "basket.Line".into() }
    }

    #[test]
    fn a_lists_domain_states_its_element_class_bound_and_the_models_digest() {
        let a = ListAdapter::new(line(), 3, false).unwrap();
        let d = a.domain();
        assert_eq!((d.kind.clone(), d.nullable, d.max_length), (ValueKind::List { element: line() }, false, 3));
        assert_eq!(a.element_class(), "basket.Line");
        assert_eq!(d.model.level, EvidenceLevel::Tested, "sampled conformance is tested, never proved");
        assert_eq!(d.model.jdk, LIST_MODEL_JDK);
        let digest = list_model_digest();
        assert_eq!(digest.len(), 64);
        assert!(d.model.source.contains(&digest), "the model's identity holds its bytecode's digest: {}", d.model.source);
        assert!(d.model.leaves_out.iter().any(|l| l.contains("ArrayList")) && d.model.leaves_out.iter().any(|l| l.contains("getClass")));
        let json = serde_json::to_value(d).unwrap();
        assert_eq!(serde_json::from_value::<ValueDomain>(json).unwrap(), *d);
        // Lists of Strings, and lists past List.of's fixed forms, are refused by name.
        assert!(ListAdapter::new(ElementKind::String, 3, false).unwrap_err().what.contains("no bound for its elements"));
        assert!(ListAdapter::new(line(), MAX_LIST_LENGTH + 1, false).unwrap_err().what.contains("array form"));
        assert!(ListAdapter::new(line(), MAX_LIST_LENGTH, false).is_ok());
    }

    #[test]
    fn a_harness_makes_a_list_by_list_of_over_the_objects_it_picks() {
        let a = ListAdapter::new(line(), 3, true).unwrap();
        assert_eq!(a.choices("lines"), ["linesNull", "linesLength", "linesPick1", "linesPick2"]);
        assert_eq!(a.admitted("lines"), "(linesNull == 0 || linesNull == 1) && 0 <= linesLength && linesLength <= 3 && 0 <= linesPick1 && linesPick1 <= 1 && 0 <= linesPick2 && linesPick2 <= 2");
        let made = ["m0".to_string(), "m1".into(), "m2".into()];
        let java = a.java("lines", "before", "before.basket.Line", &made).unwrap();
        assert_eq!(
            java,
            "before.basket.Line before0 = m0;\n\
             before.basket.Line before1 = linesPick1 == 0 ? m0 : m1;\n\
             before.basket.Line before2 = linesPick2 == 0 ? m0 : linesPick2 == 1 ? m1 : m2;\n\
             java.util.List<before.basket.Line> before = linesNull == 1 ? null : linesLength == 0 ? java.util.List.<before.basket.Line>of() : linesLength == 1 ? java.util.List.<before.basket.Line>of(before0) : linesLength == 2 ? java.util.List.<before.basket.Line>of(before0, before1) : java.util.List.<before.basket.Line>of(before0, before1, before2);\n"
        );
        assert!(a.java("lines", "after", "basket.Line", &made[..2]).is_err(), "it picks among exactly max_length made objects");
        let strict = ListAdapter::new(line(), 1, false).unwrap();
        assert_eq!(strict.choices("xs"), ["xsLength"]);
        assert_eq!(strict.admitted("xs"), "0 <= xsLength && xsLength <= 1");
    }

    #[test]
    fn a_witnessed_list_is_its_elements_as_nodes_in_order_and_never_cut() {
        let a = ListAdapter::new(line(), 3, true).unwrap();
        let made = [7, 8, 9];
        let node = |id| WitnessValue::Node { id };
        let list = |ids: &[u32]| WitnessValue::List { elements: ids.iter().map(|&i| node(i)).collect() };
        assert_eq!(a.read(&[1, 0, 0, 0], &made).unwrap(), WitnessValue::Null);
        assert_eq!(a.read(&[0, 0, 1, 2], &made).unwrap(), list(&[]));
        assert_eq!(a.read(&[0, 3, 0, 0], &made).unwrap(), list(&[7, 7, 7]), "duplicates: one object three times");
        assert_eq!(a.read(&[0, 3, 1, 1], &made).unwrap(), list(&[7, 8, 8]));
        assert_eq!(a.read(&[0, 2, 1, 5], &made).unwrap(), list(&[7, 8]), "a pick past the length is no element");
        assert!(a.read(&[0, 4, 0, 0], &made).unwrap_err().what.contains("never cut"));
        assert!(a.read(&[0, -1, 0, 0], &made).is_err());
        assert!(a.read(&[0, 2, 2, 0], &made).unwrap_err().what.contains("outside 0 to 1"));
        assert!(a.read(&[2, 0, 0, 0], &made).unwrap_err().what.contains("not 0 or 1"));
        assert!(a.read(&[0, 0, 0], &made).is_err() && a.read(&[0, 0, 0, 0], &made[..2]).is_err());
    }

    #[test]
    fn a_list_rebuilt_on_the_interpreter_is_its_list_of_and_encodes_as_the_same_nodes() {
        let cp = ClassPath::new().with_default_jdk();
        let mut m = Machine::new(&cp);
        let a = ListAdapter::new(line(), 3, true).unwrap();
        // Three objects of the plan, as a replay makes them (any object will do for the adapter: it holds identity).
        let mut nodes = Nodes::new();
        for id in [4, 5, 6] {
            let o = m.new_string(JStr::from_units(vec![id as u16]));
            nodes.insert(id, o);
        }
        let node = |id| WitnessValue::Node { id };
        let mut empties = Vec::new();
        for ids in [vec![], vec![4], vec![4, 4], vec![5, 4, 5], vec![6, 5, 4]] {
            let w = WitnessValue::List { elements: ids.iter().map(|&i| node(i)).collect() };
            let v = a.rebuild(&mut m, &w, &nodes).unwrap();
            let Value::Ref(r) = v else { panic!() };
            let expected = match ids.len() {
                0 => None,
                1 | 2 => Some(crate::interp::ImmutableList::List12),
                _ => Some(crate::interp::ImmutableList::ListN),
            };
            if let Some(kind) = expected {
                assert_eq!(m.immutable_list_kind(r), Some(kind), "{ids:?}: the JDK's class for its length");
            } else {
                empties.push(v);
            }
            assert_eq!(a.encode(&m, v, &nodes).unwrap(), w, "{ids:?}");
        }
        let again = a.rebuild(&mut m, &WitnessValue::List { elements: vec![] }, &nodes).unwrap();
        assert_eq!(again, empties[0], "the one empty list, as List.of() gives");
        assert_eq!(a.rebuild(&mut m, &WitnessValue::Null, &nodes).unwrap(), Value::Null);
        assert_eq!(a.encode(&m, Value::Null, &nodes).unwrap(), WitnessValue::Null);
        // Outside the domain: refused, never cut, copied or invented.
        let four = WitnessValue::List { elements: vec![node(4); 4] };
        assert!(a.rebuild(&mut m, &four, &nodes).unwrap_err().what.contains("beyond the domain's bound of 3"));
        let o = nodes.get(4).unwrap();
        let long = m.immutable_list(vec![o; 4]);
        assert!(a.encode(&m, long, &nodes).unwrap_err().what.contains("never cut"));
        assert!(a.rebuild(&mut m, &WitnessValue::List { elements: vec![node(9)] }, &nodes).unwrap_err().what.contains("hasn't made"));
        assert!(a.rebuild(&mut m, &WitnessValue::List { elements: vec![WitnessValue::Null] }, &nodes).is_err());
        let stranger = m.new_string(JStr::from_units(vec![1]));
        let with_stranger = m.immutable_list(vec![stranger]);
        assert!(a.encode(&m, with_stranger, &nodes).unwrap_err().what.contains("no object of the construction plan"));
        let mutable = Value::Ref(m.alloc_native(Native::List { elements: vec![o], mutable: true }));
        assert!(a.encode(&m, mutable, &nodes).unwrap_err().what.contains("java.util.ArrayList"));
        let strict = ListAdapter::new(line(), 3, false).unwrap();
        assert!(strict.encode(&m, Value::Null, &nodes).is_err() && strict.rebuild(&mut m, &WitnessValue::Null, &nodes).is_err());
    }
}
