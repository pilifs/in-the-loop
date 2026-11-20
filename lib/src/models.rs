//! The models of JDK classes that ship with the tool: class files compiled from the Java sources in `models/java`
//! and embedded here, so that a proof needs neither a models jar on the class path nor a JDK to compile one.
//!
//! JBMC 6 embeds no model of the class library. The tool hands it the real bytecode of six JDK classes
//! ([`crate::equivalence::JDK_CLASSES`]) and every other JDK class is a stub whose methods return nondeterministic
//! values and whose static fields are nondeterministic references, which under `--throw-runtime-exceptions` become
//! `NullPointerException`s and `ArrayIndexOutOfBoundsException`s on paths a JVM never takes: a class whose static
//! initializer reads `StandardCharsets.UTF_8`, or a call that boxes with `Integer.valueOf`, was reported as a
//! violation. A model is a small Java class with the behaviour that programs observe and none of the machinery:
//! JBMC reads it from the class path in place of the stub, and the interpreter runs the same bytecode in place of
//! its own natives for the methods the model defines, so that a counterexample found by one is replayed by the
//! other on the same definition.
//!
//! The catalogue, with what each model keeps and leaves out, is `models/README.md`; `models/build.sh` recompiles the
//! class files after a change, and a test checks that the embedded class files match the sources.

use std::path::Path;

use serde::Serialize;

use crate::classfile::ClassFile;
use crate::Error;

/// One modelled class.
#[derive(Debug, Clone, Serialize)]
pub struct Model {
    /// The internal name, such as `java/nio/charset/Charset`.
    pub name: &'static str,
    /// The source, relative to `models/`.
    pub source: &'static str,
    /// What the model is for, in a sentence.
    pub note: &'static str,
    /// Only on JBMC's class path: the interpreter and the tool's own checker keep their own handling of the class
    /// ([`ClassPath::model`](crate::classpath::ClassPath::model) does not give it). The interpreter's natives for
    /// these behave as the model does, which the conformance corpus checks against a JVM; they are kept because
    /// the state they stand for (an enum's name and ordinal, an immutable list's elements) is part of every object
    /// the interpreter allocates.
    pub jbmc_only: bool,
    /// Only for the tool's own checker ([`CHECKER_RUNS`]): not on JBMC's class path either, whose stubs of the
    /// class stay what they were. The stream models are, which a claim compiled by javac calls
    /// ([`crate::claim`]) and only the own checker is given.
    pub checker_only: bool,
    #[serde(skip)]
    pub bytes: &'static [u8],
}

macro_rules! model {
    ($name:literal, $source:literal, $class:literal, $note:literal) => {
        Model { name: $name, source: $source, note: $note, jbmc_only: false, checker_only: false, bytes: include_bytes!(concat!("../models/classes/", $class)) }
    };
    (jbmc $name:literal, $source:literal, $class:literal, $note:literal) => {
        Model { name: $name, source: $source, note: $note, jbmc_only: true, checker_only: false, bytes: include_bytes!(concat!("../models/classes/", $class)) }
    };
    (checker $name:literal, $source:literal, $class:literal, $note:literal) => {
        Model { name: $name, source: $source, note: $note, jbmc_only: true, checker_only: true, bytes: include_bytes!(concat!("../models/classes/", $class)) }
    };
}

/// Every model, in class path order.
pub const MODELS: &[Model] = &[
    model!("java/lang/Integer$IntegerCache", "java/lang/Integer$IntegerCache.java", "java/lang/Integer$IntegerCache.class", "the nested cache the JDK's Integer.valueOf reads, declared empty so that boxing allocates (as the CProver models do) instead of indexing a nondeterministic array"),
    model!("java/lang/Long$LongCache", "java/lang/Long$LongCache.java", "java/lang/Long$LongCache.class", "the nested cache the JDK's Long.valueOf reads, declared empty so that boxing allocates (as the CProver models do) instead of indexing a nondeterministic array"),
    model!("java/lang/Short$ShortCache", "java/lang/Short$ShortCache.java", "java/lang/Short$ShortCache.class", "the nested cache the JDK's Short.valueOf reads, declared empty so that boxing allocates (as the CProver models do) instead of indexing a nondeterministic array"),
    model!("java/lang/Byte$ByteCache", "java/lang/Byte$ByteCache.java", "java/lang/Byte$ByteCache.class", "the nested cache the JDK's Byte.valueOf reads, declared empty so that boxing allocates (as the CProver models do) instead of indexing a nondeterministic array"),
    model!("java/lang/Character", "java/lang/Character.java", "java/lang/Character.class", "digit, isDigit and forDigit from the JDK's decimal-digit table, written out as comparisons (generated from the JDK); the rest of the class is left to each engine"),
    model!("java/nio/charset/Charset", "java/nio/charset/Charset.java", "java/nio/charset/Charset.class", "a charset as a name: equality, ordering, forName and isSupported over the six standard charsets; no encoders, decoders or providers"),
    model!("java/nio/charset/StandardCharsets", "java/nio/charset/StandardCharsets.java", "java/nio/charset/StandardCharsets.class", "the six standard charsets as named instances, so that a static initializer that reads one succeeds"),
    model!("java/nio/charset/StandardCharsets$Standard", "java/nio/charset/StandardCharsets.java", "java/nio/charset/StandardCharsets$Standard.class", "the class of the six standard charsets"),
    model!("java/nio/charset/IllegalCharsetNameException", "java/nio/charset/IllegalCharsetNameException.java", "java/nio/charset/IllegalCharsetNameException.class", "the exception Charset.forName throws for a null name"),
    model!("java/nio/charset/UnsupportedCharsetException", "java/nio/charset/UnsupportedCharsetException.java", "java/nio/charset/UnsupportedCharsetException.class", "the exception Charset.forName throws for a name that is none of the six"),
    model!(jbmc "java/lang/Enum", "java/lang/Enum.java", "java/lang/Enum.class", "an enum constant's name and ordinal, set by Enum.<init>(String, int) and read by name, ordinal and toString; equals by identity; JBMC only"),
    model!(jbmc "java/util/HashMap", "java/util/HashMap.java", "java/util/HashMap.class", "a HashMap as its entries in insertion order: HashMap() and HashMap(int), get, containsKey, put, size and isEmpty, a key found by hashCode and equals as the JDK finds one; no iteration, removal or resizing; JBMC only"),
    model!(jbmc "java/util/HashMap$Node", "java/util/HashMap.java", "java/util/HashMap$Node.class", "an entry of the HashMap model: its key, the key's hash and its value; JBMC only"),
    model!(checker "java/util/IdentityHashMap", "java/util/IdentityHashMap.java", "java/util/IdentityHashMap.class", "IdentityHashMap(), put, get, containsKey and size using reference identity, including null keys and values; the own checker only"),
    model!(checker "java/util/IdentityHashMap$Binding", "java/util/IdentityHashMap.java", "java/util/IdentityHashMap$Binding.class", "one private binding of the native identity-key map model"),
    model!(checker "java/util/LinkedHashMap", "java/util/LinkedHashMap.java", "java/util/LinkedHashMap.class", "a LinkedHashMap as the HashMap model's entries, iterated in insertion order: LinkedHashMap(), what the HashMap model has, and values() with its size and fail-fast iterator; the own checker only"),
    model!(checker "java/util/LinkedHashMap$LinkedValues", "java/util/LinkedHashMap.java", "java/util/LinkedHashMap$LinkedValues.class", "the values collection of the LinkedHashMap model: size and iterator; the own checker only"),
    model!(checker "java/util/LinkedHashMap$LinkedValueIterator", "java/util/LinkedHashMap.java", "java/util/LinkedHashMap$LinkedValueIterator.class", "the iterator of the LinkedHashMap model's values: hasNext and next, fail-fast; the own checker only"),
    model!(checker "java/util/ArrayAsList", "java/util/lists/ArrayAsList.java", "java/util/ArrayAsList.class", "what Arrays.asList(T...) returns: a list that is a view of the array, with size, get and toArray(); not a JDK class; the own checker only"),
    model!(checker "java/util/ArrayList", "java/util/lists/ArrayList.java", "java/util/ArrayList.class", "an ArrayList as an array of its elements and their number: ArrayList() and ArrayList(int), size, isEmpty, get, add, addAll, remove(Object), toArray() and toArray(T[]), and iterator() with its fail-fast iterator; run only for a check that asks for it (--model java.util.ArrayList); the own checker only"),
    model!(checker "java/util/ArrayList$Itr", "java/util/lists/ArrayList.java", "java/util/ArrayList$Itr.class", "the iterator of the ArrayList model: hasNext and next, fail-fast; the own checker only"),
    model!(checker "java/util/HashSet", "java/util/lists/HashSet.java", "java/util/HashSet.class", "a HashSet as the keys of the HashMap model, as the JDK's: HashSet(), add, contains, size and isEmpty, an element found by hashCode and equals; run only for a check that asks for it (--model java.util.HashSet); the own checker only"),
    model!(checker "java/util/concurrent/ConcurrentHashMap", "java/util/concurrent/ConcurrentHashMap.java", "java/util/concurrent/ConcurrentHashMap.class", "single-threaded ConcurrentHashMap() and ConcurrentHashMap(int), get, putIfAbsent, size and isEmpty with String keys, non-null values and the JDK exception classes for null inputs; the own checker only, on request"),
    model!(checker "java/util/LinkedHashSet", "java/util/lists/LinkedHashSet.java", "java/util/LinkedHashSet.class", "a LinkedHashSet as the HashSet model with its elements in the order first added: LinkedHashSet(), add, toArray() and toArray(T[]) in that order, and the HashSet model's contains, size and isEmpty; run only for a check that asks for it (--model java.util.LinkedHashSet), which runs the HashSet model too; the own checker only"),
    model!(checker "java/util/StringJoiner", "java/util/lists/StringJoiner.java", "java/util/StringJoiner.class", "a StringJoiner as its delimiter and the elements added: StringJoiner(CharSequence), add, and toString joining them with the delimiter into a new String (an empty one is the JDK's new String()); run only for a check that asks for it (--model java.util.StringJoiner); the own checker only"),
    model!(checker "java/util/ArrayDeque", "java/util/lists/ArrayDeque.java", "java/util/ArrayDeque.class", "an ArrayDeque used as a stack, its elements in an array: ArrayDeque(), push (NullPointerException for null), pop (NoSuchElementException when empty), peek, size, isEmpty and clear; run only for a check that asks for it (--model java.util.ArrayDeque); the own checker only"),
    model!(checker "java/beans/PropertyChangeEvent", "java/beans/PropertyChangeEvent.java", "java/beans/PropertyChangeEvent.class", "a PropertyChangeEvent as its fields: the constructor, getPropertyName, getNewValue, getOldValue and the propagation id, the source kept by the model of EventObject; run only for a check that asks for it (--model java.beans.PropertyChangeEvent); the own checker only"),
    model!(checker "java/util/EventObject", "java/beans/EventObject.java", "java/util/EventObject.class", "an EventObject as its source: the constructor (IllegalArgumentException for a null source) and getSource; run with the model of PropertyChangeEvent and only for a check that asks for that one; the own checker only"),
    model!(jbmc "java/util/List", "java/util/List.java", "java/util/List.class", "the static factories of and copyOf, step for step as the JDK's: immutable lists, NullPointerException on a null element, copyOf of one of them the list itself; JBMC only"),
    model!(jbmc "java/util/ImmutableCollections", "java/util/ImmutableCollections.java", "java/util/ImmutableCollections.class", "the list factories' helpers and the one empty list; JBMC only"),
    model!(jbmc "java/util/ImmutableCollections$AbstractImmutableList", "java/util/ImmutableCollections.java", "java/util/ImmutableCollections$AbstractImmutableList.class", "an immutable list: every change throws UnsupportedOperationException; iterator, equals, hashCode and contains over the elements; JBMC only"),
    model!(jbmc "java/util/ImmutableCollections$ListItr", "java/util/ImmutableCollections.java", "java/util/ImmutableCollections$ListItr.class", "the immutable lists' iterator: NoSuchElementException past the end, UnsupportedOperationException on remove; JBMC only"),
    model!(jbmc "java/util/ImmutableCollections$List12", "java/util/ImmutableCollections.java", "java/util/ImmutableCollections$List12.class", "an immutable list of one or two elements, as the JDK's; JBMC only"),
    model!(jbmc "java/util/ImmutableCollections$ListN", "java/util/ImmutableCollections.java", "java/util/ImmutableCollections$ListN.class", "an immutable list of none or three or more elements over an array of its own, as the JDK's; JBMC only"),
    model!(checker "java/util/stream/Stream", "java/util/stream/Stream.java", "java/util/stream/Stream.class", "a sequential stream's allMatch, anyMatch, noneMatch, map and toArray(IntFunction), declared for the model's stream over an array; the own checker only"),
    model!(checker "java/util/stream/SequentialArrayStream", "java/util/stream/SequentialArrayStream.java", "java/util/stream/SequentialArrayStream.class", "what Arrays.stream(T[]) returns: the array's elements one at a time through each map, a match stopped where it is decided, a stream used once; not a JDK class; the own checker only"),
    model!(checker "java/util/stream/IntStream", "java/util/stream/IntStream.java", "java/util/stream/IntStream.class", "an int stream's allMatch, anyMatch and noneMatch, declared for the models' streams of a String's code units, of a range of ints and of an array of ints; the own checker only"),
    model!(checker "java/util/stream/CharsStream", "java/util/stream/CharsStream.java", "java/util/stream/CharsStream.class", "what String.chars() returns: the code units in order, each zero-extended; not a JDK class; the own checker only"),
    model!(checker "java/util/stream/RangeStream", "java/util/stream/RangeStream.java", "java/util/stream/RangeStream.class", "what IntStream.range(int, int) returns: the ints from the start up to the end, in order; not a JDK class; the own checker only"),
    model!(checker "java/util/stream/IntArrayStream", "java/util/stream/IntArrayStream.java", "java/util/stream/IntArrayStream.class", "what Arrays.stream(int[]) returns: the array's ints in order; not a JDK class; the own checker only"),
];

/// The models only for JBMC's class path ([`Model::jbmc_only`]) that the tool's own checker runs as bytecode all the
/// same ([`ClassPath::checker_model`](crate::classpath::ClassPath::checker_model)): `java.lang.Enum`, whose
/// constructor and accessors an enum's initializer and methods call, and the immutable lists `List.of` and
/// `List.copyOf` make (`List`'s factories, `ImmutableCollections`, its `List12`, `ListN`, `AbstractImmutableList` and
/// `ListItr`), written without a JDK call so that the checker runs every step as JBMC does, and `java.util.HashMap`
/// with its entries (`HashMap$Node`), whose only calls out are its keys' `hashCode` and `equals`, and
/// `java.util.LinkedHashMap` over it, with its values and their iterator, and the list `Arrays.asList` returns,
/// a view of its array. Their state is fields of
/// their own objects (an enum's name and ordinal, a list's elements) and `ImmutableCollections`' two statics (the one
/// empty list, the sentinel of a list of one), which the checker holds as an application class's
/// ([`ClassPath::checker_class`](crate::classpath::ClassPath::checker_class)); the interpreter keeps its natives for
/// these classes, which the conformance corpus checks against a JVM.
pub const CHECKER_RUNS: &[&str] = &[
    "java/lang/Enum",
    "java/util/HashMap",
    "java/util/HashMap$Node",
    "java/util/IdentityHashMap",
    "java/util/IdentityHashMap$Binding",
    "java/util/LinkedHashMap",
    "java/util/LinkedHashMap$LinkedValues",
    "java/util/LinkedHashMap$LinkedValueIterator",
    "java/util/ArrayAsList",
    "java/util/List",
    "java/util/ImmutableCollections",
    "java/util/ImmutableCollections$AbstractImmutableList",
    "java/util/ImmutableCollections$ListItr",
    "java/util/ImmutableCollections$List12",
    "java/util/ImmutableCollections$ListN",
    "java/util/stream/Stream",
    "java/util/stream/SequentialArrayStream",
    "java/util/stream/IntStream",
    "java/util/stream/CharsStream",
    "java/util/stream/RangeStream",
    "java/util/stream/IntArrayStream",
];

/// The single-threaded String-key registry model.
pub const CONCURRENT_MAP: &str = "java/util/concurrent/ConcurrentHashMap";

/// The models the own checker runs only for a check that asks for one (`prove --model CLASS`,
/// [`ClassPath::runs_model`](crate::classpath::ClassPath::runs_model)), each with the classes nested in it:
/// otherwise the class is the JDK's, whose constructors and methods are the JDK calls they were (gaps, with their
/// contracts). `java.util.ArrayList` is one because its constructor `ArrayList(int)` is the gap the contract
/// library, the conformance corpus and the examples' recorded refusals are written about: a check that needs what
/// a list holds asks for the model, and its result says so ([`requested_assumption`]). `java.util.ArrayDeque` is
/// one for the same reason, and `java.util.HashSet`: their constructors are gaps of every binding result Spring's
/// `AbstractErrors` and `AbstractBindingResult` make (example 286, `DataBinder.bind`). `java.util.LinkedHashSet` is
/// one for the message codes Spring's `DefaultMessageCodesResolver` collects for each binding error, and runs the
/// `HashSet` model above it ([`BRINGS`]), and `java.util.StringJoiner` for each code it joins. `java.beans.PropertyChangeEvent`
/// is one for the event the bean wrapper makes for a value it cannot convert, and brings the model of the class above
/// it, `java.util.EventObject` ([`COMPANIONS`]).
pub const ON_REQUEST: &[&str] = &["java/util/ArrayList", "java/util/ArrayDeque", "java/util/HashSet", "java/util/LinkedHashSet", "java/util/StringJoiner", "java/beans/PropertyChangeEvent", CONCURRENT_MAP];

/// The models on request a check that asks for another also runs, as if it had asked for them too: the model above
/// it that it extends and whose constructor and methods it calls, itself a model on request of its own
/// (`java.util.LinkedHashSet` over `java.util.HashSet`). Unlike a companion ([`COMPANIONS`]), such a model may be
/// asked for alone, and its result then names it alone.
pub const BRINGS: &[(&str, &str)] = &[("java/util/LinkedHashSet", "java/util/HashSet")];

/// The models run with a model on request and only with it, each with the one it comes with: a class above the
/// model whose constructor the model's calls.
pub const COMPANIONS: &[(&str, &str)] = &[("java/util/EventObject", "java/beans/PropertyChangeEvent")];

/// The model on request a class belongs to: the class itself, the one it is nested in, or the one it comes with
/// ([`COMPANIONS`]).
pub fn on_request(name: &str) -> Option<&'static str> {
    if let Some((_, with)) = COMPANIONS.iter().find(|(c, _)| *c == name) {
        return Some(with);
    }
    ON_REQUEST.iter().copied().find(|r| name == *r || name.strip_prefix(r).is_some_and(|rest| rest.starts_with('$')))
}

/// The internal names of the models `--model CLASS` runs: the one it asks for and those that one brings
/// ([`BRINGS`]); or what to say when there is none.
pub fn requested(class: &str) -> Result<Vec<&'static str>, Error> {
    let name = class.replace('.', "/");
    let model = ON_REQUEST.iter().copied().find(|r| *r == name);
    model.map(|m| std::iter::once(m).chain(BRINGS.iter().filter(|(by, _)| *by == m).map(|(_, brought)| *brought)).collect()).ok_or_else(|| Error::new(format!("--model {class}: no model on request of that class; there is one of {}", ON_REQUEST.iter().map(|r| r.replace('/', ".")).collect::<Vec<_>>().join(", "))))
}

/// What a result rests on when its check asked for a model ([`ON_REQUEST`]), in the words it states.
pub fn requested_assumption(model: &str) -> String {
    let m = find(model).expect("a model on request is a model");
    format!("{} is the tool's model of the class wherever the check runs it (--model), not the JDK's code: {} (lib/models/{}); a constructor or method the model does not keep is the JDK call it names", model.replace('/', "."), m.note.split(';').next().unwrap_or(m.note), m.source)
}

/// The JDK calls that enter a model by a method of the model's own: `java.util.Arrays.stream(T[])`,
/// `Arrays.stream(int[])`, `Arrays.asList(T...)`, `String.chars()` and `IntStream.range(int, int)`, whose classes
/// the tool does not model otherwise. Each is the model's static method
/// `(class, name, descriptor)`, called with the call's receiver, if it has one, and its arguments.
pub fn entry(owner: &str, name: &str, descriptor: &str) -> Option<(&'static str, &'static str, &'static str)> {
    match (owner, name, descriptor) {
        ("java/util/Arrays", "stream", "([Ljava/lang/Object;)Ljava/util/stream/Stream;")
        | ("java/util/stream/Stream", "of", "([Ljava/lang/Object;)Ljava/util/stream/Stream;") => Some(("java/util/stream/SequentialArrayStream", "of", "([Ljava/lang/Object;)Ljava/util/stream/Stream;")),
        ("java/lang/String", "chars", "()Ljava/util/stream/IntStream;") => Some(("java/util/stream/CharsStream", "of", "(Ljava/lang/String;)Ljava/util/stream/IntStream;")),
        ("java/util/stream/IntStream", "range", "(II)Ljava/util/stream/IntStream;") => Some(("java/util/stream/RangeStream", "of", "(II)Ljava/util/stream/IntStream;")),
        ("java/util/Arrays", "stream", "([I)Ljava/util/stream/IntStream;") => Some(("java/util/stream/IntArrayStream", "of", "([I)Ljava/util/stream/IntStream;")),
        ("java/util/Arrays", "asList", "([Ljava/lang/Object;)Ljava/util/List;") => Some(("java/util/ArrayAsList", "of", "([Ljava/lang/Object;)Ljava/util/List;")),
        _ => None,
    }
}

/// Whether a class is one of the immutable-list models the own checker runs ([`CHECKER_RUNS`]): `java.util.List`
/// and `java.util.ImmutableCollections` with its list classes. A call into one of them from outside them runs only
/// where an evidence record of the values stream samples it ([`crate::values::samples_list_call`]); any other is the
/// JDK call it names, a gap ([`crate::bmc::gaps::outside_the_list_records`]).
pub fn of_the_list_family(name: &str) -> bool {
    name == "java/util/List" || name == "java/util/ImmutableCollections" || name.starts_with("java/util/ImmutableCollections$")
}

/// The model of a class, by internal name, whichever engines run it.
pub fn find(name: &str) -> Option<&'static Model> {
    MODELS.iter().find(|m| m.name == name)
}

/// The class file of a model, parsed.
pub fn class(name: &str) -> Result<Option<ClassFile>, Error> {
    find(name).map(|m| ClassFile::parse(m.bytes).map_err(|e| Error::new(format!("the model of {name} does not parse: {e}")))).transpose()
}

/// Writes every model's class file under `dir`, as `dir/java/lang/Character.class` and so on: a class path entry
/// for JBMC, or for any other tool that reads class files.
pub fn write_to(dir: &Path) -> Result<(), Error> {
    crate::phases::timed(crate::phases::Step::Setup, || write_to_untimed(dir))
}

fn write_to_untimed(dir: &Path) -> Result<(), Error> {
    for model in MODELS.iter().filter(|m| !m.checker_only) {
        let target = dir.join(format!("{}.class", model.name));
        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(&target, model.bytes)?;
    }
    Ok(())
}

/// The catalogue as text: one line per model.
pub fn listing() -> String {
    let mut s = String::new();
    for model in MODELS {
        s.push_str(&format!("{}  ({})\n    {}\n", model.name.replace('/', "."), model.source, model.note));
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_model_parses_as_the_class_it_names() {
        for model in MODELS {
            let class = ClassFile::parse(model.bytes).unwrap_or_else(|e| panic!("{}: {e}", model.name));
            assert_eq!(class.name, model.name);
            assert_eq!(class.major, 52, "{}: compiled for Java 8, which JBMC 6 reads", model.name);
        }
        assert!(find("java/lang/Character").is_some());
        assert!(find("java/lang/Integer").is_none(), "the real Integer is extracted from the JDK, not modelled");
        assert!(class("java/nio/charset/Charset").unwrap().unwrap().methods.iter().any(|m| m.name == "forName"));
    }

    #[test]
    fn the_models_are_written_as_a_class_path_entry() {
        let dir = tempfile::tempdir().unwrap();
        write_to(dir.path()).unwrap();
        for model in MODELS {
            let written = dir.path().join(format!("{}.class", model.name));
            // A model only the checker runs is no class of JBMC's class path.
            if model.checker_only {
                assert!(!written.exists(), "{}", model.name);
            } else {
                assert_eq!(std::fs::read(written).unwrap(), model.bytes);
            }
        }
        assert!(listing().contains("java.nio.charset.StandardCharsets  (java/nio/charset/StandardCharsets.java)"));
    }

    /// The embedded class files are what `models/build.sh` makes of the sources: a model edited without a rebuild
    /// fails here. Compared as disassembly, so that a javac of another version that lays out a constant pool
    /// differently does not fail it.
    #[test]
    fn the_embedded_class_files_match_their_sources() {
        crate::tool_tier!();
        let javac = std::process::Command::new("javac").arg("-version").output().is_ok_and(|o| o.status.success());
        if !javac {
            assert!(std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1"), "javac not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip this test");
            eprintln!("javac not found; skipping");
            return;
        }
        let models = Path::new(env!("CARGO_MANIFEST_DIR")).join("models");
        let out = tempfile::tempdir().unwrap();
        // `util/lists` and `beans` are compiled against the JDK's `List`, as `build.sh` compiles them: with no source
        // path.
        for package in ["lang", "nio/charset", "util", "util/stream", "util/lists", "util/concurrent", "beans"] {
            let sources: Vec<_> = std::fs::read_dir(models.join("java").join(package)).unwrap().map(|e| e.unwrap().path()).filter(|p| p.extension().is_some_and(|e| e == "java")).collect();
            let alone: &[&str] = if matches!(package, "util/lists" | "util/concurrent" | "beans") { &["-sourcepath", ""] } else { &[] };
            let status = std::process::Command::new("javac").args(["--release", "8", "-Xlint:-options", "-g"]).args(alone).arg("-d").arg(out.path()).args(&sources).status().unwrap();
            assert!(status.success(), "the models compile");
        }
        for model in MODELS {
            let compiled = std::fs::read(out.path().join(format!("{}.class", model.name))).unwrap_or_else(|e| panic!("{}: {e}", model.name));
            let fresh = crate::classfile::describe(&ClassFile::parse(&compiled).unwrap(), true).unwrap();
            let embedded = crate::classfile::describe(&ClassFile::parse(model.bytes).unwrap(), true).unwrap();
            let body = |s: &str| s.lines().skip(1).collect::<Vec<_>>().join("\n");
            assert_eq!(body(&embedded), body(&fresh), "{}: models/classes is stale; run models/build.sh", model.name);
        }
    }
}
