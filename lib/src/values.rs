//! The values stream's module (`llm-dlc/loops/application-core-values.md`): value adapters for bounded Strings and
//! one bounded immutable-list family, used by object construction, by result and field observation, by effect
//! snapshots and by JVM replay. Registered by Phase 0 of `llm-dlc/loops/application-core.md`, so that the stream
//! starts without editing a shared file. Until the stream builds an adapter, [`adapter`] returns [`Unsupported`]
//! naming it, and every call site keeps refusing the value it would have handled.

use crate::classfile::Type;
use crate::interp::{Machine, Value};
use crate::spec::plans::{ValueDomain, WitnessValue};
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
/// elements or code units, if the stream has built one. Asked where a check meets a `String` or a `List`; its
/// refusal is added to the check's.
pub fn adapter(ty: &Type, max_length: u32) -> Result<Box<dyn ValueAdapter>, Unsupported> {
    let _ = max_length;
    Err(Unsupported::new(Part::Values, format!("a value adapter for {}: the values stream builds it (llm-dlc/loops/application-core-values.md)", ty.java_name())))
}

/// Whether `ty` is one the values stream's adapters are for: a String, or a `java.util.List`. Every other type is
/// another stream's or unsupported, and [`adapter`] isn't asked.
pub fn is_adapted(ty: &Type) -> bool {
    matches!(ty, Type::Object(name) if name == "java/lang/String" || name == "java/util/List")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_string_or_a_list_is_refused_by_name_until_the_stream_builds_its_adapter() {
        for name in ["java/lang/String", "java/util/List"] {
            let ty = Type::Object(name.into());
            assert!(is_adapted(&ty));
            let gap = adapter(&ty, 8).err().expect("no adapter yet");
            assert_eq!(gap.part, Part::Values);
            assert!(gap.what.contains(&format!("a value adapter for {}", name.replace('/', "."))), "{gap}");
        }
        assert!(!is_adapted(&Type::Int) && !is_adapted(&Type::Object("shop/Quote".into())));
    }
}
