//! JDK methods trusted to be pure: deterministic, and without effects beyond the objects they create. Everything
//! else in the JDK is rejected by the purity analysis, including the clock, randomness, I/O, threads, reflection
//! and system properties. This list is the trusted base of every behavioural contract; keep it short and review
//! additions.
//!
//! The list is the *static* trusted base. Every execution also runs under the interpreter's effect monitor, which
//! models each of these methods natively and refuses anything else, so a call trusted here that the interpreter
//! does not model still cannot produce a contract. Functional interfaces (`java.util.function`) are trusted on
//! that basis: calling one runs a lambda whose implementation the analysis walked when it was created, or an
//! application class, and either runs under the monitor.

const IMMUTABLE_TYPES: &[&str] = &[
    "java/lang/String",
    "java/lang/Math",
    "java/lang/StrictMath",
    "java/util/Objects",
    "java/lang/Integer",
    "java/lang/Long",
    "java/lang/Short",
    "java/lang/Byte",
    "java/lang/Boolean",
    "java/lang/Character",
    "java/lang/Double",
    "java/lang/Float",
    "java/util/Optional",
    // Mutable, but only ever a method's own: the effect monitor refuses writes to a builder that existed before
    // the call, and `toString` is the only way its content leaves the method.
    "java/lang/StringBuilder",
];

const COLLECTION_TYPES: &[&str] = &["java/util/List", "java/util/Set", "java/util/Map"];

const COLLECTION_READS: &[&str] = &[
    "of", "copyOf", "size", "isEmpty", "get", "getOrDefault", "contains", "containsAll", "containsKey", "containsValue",
    "equals", "hashCode", "indexOf", "lastIndexOf", "iterator", "forEach", "keySet", "values", "getFirst", "getLast",
];

const ENUM_METHODS: &[&str] = &["<init>", "ordinal", "name", "equals", "hashCode", "compareTo", "valueOf"];

/// Whether a call to `owner.name` is trusted to be pure.
pub fn is_pure(owner: &str, name: &str) -> bool {
    if IMMUTABLE_TYPES.contains(&owner) {
        return name != "random";
    }
    if COLLECTION_TYPES.contains(&owner) {
        return COLLECTION_READS.contains(&name);
    }
    if owner.starts_with("java/util/function/") {
        return true;
    }
    match owner {
        "java/lang/Object" | "java/lang/Record" => name == "<init>",
        "java/lang/Enum" => ENUM_METHODS.contains(&name),
        "java/util/Iterator" => matches!(name, "hasNext" | "next"),
        // Constructing an exception records a stack trace, which is not part of any outcome a contract compares.
        _ => owner.starts_with("java/lang/") && (owner.ends_with("Exception") || owner.ends_with("Error")) && name == "<init>",
    }
}

/// Bootstrap methods of `invokedynamic` that are trusted: they build pure call sites (string concatenation,
/// record `equals`/`hashCode`/`toString`, pattern-matching `switch` dispatch).
pub fn is_pure_bootstrap(owner: &str) -> bool {
    matches!(owner, "java/lang/runtime/SwitchBootstraps" | "java/lang/runtime/ObjectMethods" | "java/lang/invoke/StringConcatFactory")
}

/// Every `(owner, name)` the list trusts, for documentation and for the test that the interpreter models each.
pub fn entries() -> Vec<(&'static str, &'static str)> {
    let mut out = Vec::new();
    for owner in COLLECTION_TYPES {
        for name in COLLECTION_READS {
            out.push((*owner, *name));
        }
    }
    for name in ENUM_METHODS {
        out.push(("java/lang/Enum", *name));
    }
    out.push(("java/lang/Object", "<init>"));
    out.push(("java/lang/Record", "<init>"));
    out
}

pub fn immutable_types() -> &'static [&'static str] {
    IMMUTABLE_TYPES
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_list_is_as_documented() {
        assert!(is_pure("java/lang/Math", "multiplyExact"));
        assert!(!is_pure("java/lang/Math", "random"));
        assert!(is_pure("java/util/List", "of"));
        assert!(!is_pure("java/util/List", "add"));
        assert!(is_pure("java/lang/IllegalArgumentException", "<init>"));
        assert!(!is_pure("java/lang/IllegalArgumentException", "getMessage"));
        assert!(!is_pure("java/time/Instant", "now"));
        assert!(!is_pure("java/lang/System", "nanoTime"));
    }
}
