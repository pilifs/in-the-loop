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
    #[serde(skip)]
    pub bytes: &'static [u8],
}

macro_rules! model {
    ($name:literal, $source:literal, $class:literal, $note:literal) => {
        Model { name: $name, source: $source, note: $note, jbmc_only: false, bytes: include_bytes!(concat!("../models/classes/", $class)) }
    };
    (jbmc $name:literal, $source:literal, $class:literal, $note:literal) => {
        Model { name: $name, source: $source, note: $note, jbmc_only: true, bytes: include_bytes!(concat!("../models/classes/", $class)) }
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
    model!(jbmc "java/util/List", "java/util/List.java", "java/util/List.class", "the static factories of and copyOf, step for step as the JDK's: immutable lists, NullPointerException on a null element, copyOf of one of them the list itself; JBMC only"),
    model!(jbmc "java/util/ImmutableCollections", "java/util/ImmutableCollections.java", "java/util/ImmutableCollections.class", "the list factories' helpers and the one empty list; JBMC only"),
    model!(jbmc "java/util/ImmutableCollections$AbstractImmutableList", "java/util/ImmutableCollections.java", "java/util/ImmutableCollections$AbstractImmutableList.class", "an immutable list: every change throws UnsupportedOperationException; iterator, equals, hashCode and contains over the elements; JBMC only"),
    model!(jbmc "java/util/ImmutableCollections$ListItr", "java/util/ImmutableCollections.java", "java/util/ImmutableCollections$ListItr.class", "the immutable lists' iterator: NoSuchElementException past the end, UnsupportedOperationException on remove; JBMC only"),
    model!(jbmc "java/util/ImmutableCollections$List12", "java/util/ImmutableCollections.java", "java/util/ImmutableCollections$List12.class", "an immutable list of one or two elements, as the JDK's; JBMC only"),
    model!(jbmc "java/util/ImmutableCollections$ListN", "java/util/ImmutableCollections.java", "java/util/ImmutableCollections$ListN.class", "an immutable list of none or three or more elements over an array of its own, as the JDK's; JBMC only"),
];

/// The models only for JBMC's class path ([`Model::jbmc_only`]) that the tool's own checker runs as bytecode all the
/// same ([`ClassPath::checker_model`](crate::classpath::ClassPath::checker_model)): `java.lang.Enum`, whose
/// constructor and accessors an enum's initializer and methods call, and the immutable lists `List.of` and
/// `List.copyOf` make (`List`'s factories, `ImmutableCollections`, its `List12`, `ListN`, `AbstractImmutableList` and
/// `ListItr`), written without a JDK call so that the checker runs every step as JBMC does. Their state is fields of
/// their own objects (an enum's name and ordinal, a list's elements) and `ImmutableCollections`' two statics (the one
/// empty list, the sentinel of a list of one), which the checker holds as an application class's
/// ([`ClassPath::checker_class`](crate::classpath::ClassPath::checker_class)); the interpreter keeps its natives for
/// these classes, which the conformance corpus checks against a JVM.
pub const CHECKER_RUNS: &[&str] = &[
    "java/lang/Enum",
    "java/util/List",
    "java/util/ImmutableCollections",
    "java/util/ImmutableCollections$AbstractImmutableList",
    "java/util/ImmutableCollections$ListItr",
    "java/util/ImmutableCollections$List12",
    "java/util/ImmutableCollections$ListN",
];

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
    for model in MODELS {
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
            assert_eq!(std::fs::read(dir.path().join(format!("{}.class", model.name))).unwrap(), model.bytes);
        }
        assert!(listing().contains("java.nio.charset.StandardCharsets  (java/nio/charset/StandardCharsets.java)"));
    }

    /// The embedded class files are what `models/build.sh` makes of the sources: a model edited without a rebuild
    /// fails here. Compared as disassembly, so that a javac of another version that lays out a constant pool
    /// differently does not fail it.
    #[test]
    fn the_embedded_class_files_match_their_sources() {
        let javac = std::process::Command::new("javac").arg("-version").output().is_ok_and(|o| o.status.success());
        if !javac {
            assert!(std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1"), "javac not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip this test");
            eprintln!("javac not found; skipping");
            return;
        }
        let models = Path::new(env!("CARGO_MANIFEST_DIR")).join("models");
        let out = tempfile::tempdir().unwrap();
        for package in ["lang", "nio/charset", "util"] {
            let sources: Vec<_> = std::fs::read_dir(models.join("java").join(package)).unwrap().map(|e| e.unwrap().path()).filter(|p| p.extension().is_some_and(|e| e == "java")).collect();
            let status = std::process::Command::new("javac").args(["--release", "8", "-Xlint:-options", "-g", "-d"]).arg(out.path()).args(&sources).status().unwrap();
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
