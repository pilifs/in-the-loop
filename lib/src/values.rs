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
//! Until a check takes an adapter's values (its harness declares the parameter, passes the bound to the checker and
//! rebuilds the witness through [`StringAdapter::read`] and [`ValueAdapter::rebuild`]), [`adapter`] refuses, naming
//! the values stream, and every call site keeps refusing the value it would have handled. A list is refused until
//! the stream builds its adapter (V2).

use std::collections::BTreeMap;

use crate::classfile::Type;
use crate::interp::{JStr, Machine, Value};
use crate::spec::plans::{EvidenceLevel, ModelEvidence, ValueDomain, ValueKind, WitnessValue};
use crate::spec::{Part, Unsupported};

/// One kind of value a check can make symbolic, compare, snapshot, encode in a witness and rebuild for replay. Each
/// implementation declares its domain: its bounds, and the evidence its model has.
pub trait ValueAdapter {
    /// The domain it makes values of.
    fn domain(&self) -> &ValueDomain;
    /// A concrete value the interpreter holds, as a witness holds it.
    fn encode(&self, machine: &Machine<'_>, value: Value) -> Result<WitnessValue, Unsupported>;
    /// The value a witness holds, made on `machine` for a replay.
    fn rebuild(&self, machine: &mut Machine<'_>, witness: &WitnessValue) -> Result<Value, Unsupported>;
}

/// The adapter for values of `ty` (a parameter's, a field's, a result's or a payload's), of at most `max_length`
/// elements or code units, if a check can take it. Asked where a check meets a `String` or a `List`; its refusal
/// is added to the check's.
///
/// A String's adapter is built ([`StringAdapter`]), but no check's harness declares a String parameter, passes its
/// bound to the checker or rebuilds its witness yet: that wiring is in the checks' harness and replay (an interface
/// request of the values stream to the objects stream), so the hook still refuses it, rather than let a check say
/// it has an adapter it can't use.
pub fn adapter(ty: &Type, max_length: u32) -> Result<Box<dyn ValueAdapter>, Unsupported> {
    let _ = max_length;
    if matches!(ty, Type::Object(name) if name == STRING) {
        return Err(Unsupported::new(Part::Values, "a java.lang.String in this check: its value adapter is built (values::StringAdapter), and the values stream builds it into the checks once their harness declares a String parameter, passes its bound to the own checker (bmc::Parameters::max_string_length) and rebuilds its witness in the replay (llm-dlc/loops/application-core-values.md)"));
    }
    Err(Unsupported::new(Part::Values, format!("a value adapter for {}: the values stream builds it (llm-dlc/loops/application-core-values.md)", ty.java_name())))
}

/// Whether `ty` is one the values stream's adapters are for: a String, or a `java.util.List`. Every other type is
/// another stream's or unsupported, and [`adapter`] isn't asked.
pub fn is_adapted(ty: &Type) -> bool {
    matches!(ty, Type::Object(name) if name == STRING || name == "java/util/List")
}

const STRING: &str = "java/lang/String";

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

    fn encode(&self, machine: &Machine<'_>, value: Value) -> Result<WitnessValue, Unsupported> {
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

    fn rebuild(&self, machine: &mut Machine<'_>, witness: &WitnessValue) -> Result<Value, Unsupported> {
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::classpath::ClassPath;

    #[test]
    fn a_list_is_refused_by_name_until_the_stream_builds_its_adapter_and_a_string_until_a_check_takes_one() {
        for name in ["java/lang/String", "java/util/List"] {
            let ty = Type::Object(name.into());
            assert!(is_adapted(&ty));
            let gap = adapter(&ty, 8).err().expect("no check takes one yet");
            assert_eq!(gap.part, Part::Values);
            assert!(gap.what.contains("the values stream builds it"), "{gap}");
        }
        let list = adapter(&Type::Object("java/util/List".into()), 8).err().unwrap();
        assert!(list.what.contains("a value adapter for java.util.List"), "{list}");
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
        for units in [vec![], vec![0], vec![0xD83D, 0xDE00], vec![0xDC00, 0xD800, 0xFFFF, 0x41]] {
            let w = WitnessValue::String { units: units.clone() };
            let v = a.rebuild(&mut m, &w).unwrap();
            assert_eq!(m.units_of(v).unwrap().units(), &units[..]);
            assert_eq!(a.encode(&m, v).unwrap(), w);
        }
        assert_eq!(a.rebuild(&mut m, &WitnessValue::Null).unwrap(), Value::Null);
        assert_eq!(a.encode(&m, Value::Null).unwrap(), WitnessValue::Null);
        let five = WitnessValue::String { units: vec![1; 5] };
        assert!(a.rebuild(&mut m, &five).unwrap_err().what.contains("beyond the domain's bound of 4"));
        let long = m.new_string(JStr::from_units(vec![1; 5]));
        assert!(a.encode(&m, long).unwrap_err().what.contains("never cut"));
        assert!(a.encode(&m, Value::Int(3)).is_err());
        assert!(a.rebuild(&mut m, &WitnessValue::Node { id: 1 }).is_err());
        let strict = StringAdapter::new(4, false);
        assert!(strict.encode(&m, Value::Null).is_err() && strict.rebuild(&mut m, &WitnessValue::Null).is_err());
    }
}
