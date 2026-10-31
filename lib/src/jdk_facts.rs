//! Built-in facts about `java.base` for when no JDK image is available: the superclass, interfaces, finality and
//! declared method names of the classes the analyses and the interpreter's models refer to. With a JDK image on
//! hand ([`crate::jimage`]), the real class files take precedence.

/// `(class, superclass)`.
const SUPERCLASSES: &[(&str, &str)] = &[
    ("java/lang/Throwable", "java/lang/Object"),
    ("java/lang/Exception", "java/lang/Throwable"),
    ("java/lang/Error", "java/lang/Throwable"),
    ("java/lang/RuntimeException", "java/lang/Exception"),
    ("java/lang/ReflectiveOperationException", "java/lang/Exception"),
    ("java/lang/ClassNotFoundException", "java/lang/ReflectiveOperationException"),
    ("java/lang/InterruptedException", "java/lang/Exception"),
    ("java/lang/CloneNotSupportedException", "java/lang/Exception"),
    ("java/io/IOException", "java/lang/Exception"),
    ("java/io/UncheckedIOException", "java/lang/RuntimeException"),
    ("java/lang/IllegalArgumentException", "java/lang/RuntimeException"),
    ("java/lang/IllegalStateException", "java/lang/RuntimeException"),
    ("java/lang/NullPointerException", "java/lang/RuntimeException"),
    ("java/lang/ArithmeticException", "java/lang/RuntimeException"),
    ("java/lang/ClassCastException", "java/lang/RuntimeException"),
    ("java/lang/IndexOutOfBoundsException", "java/lang/RuntimeException"),
    ("java/lang/ArrayIndexOutOfBoundsException", "java/lang/IndexOutOfBoundsException"),
    ("java/lang/StringIndexOutOfBoundsException", "java/lang/IndexOutOfBoundsException"),
    ("java/lang/NumberFormatException", "java/lang/IllegalArgumentException"),
    ("java/lang/UnsupportedOperationException", "java/lang/RuntimeException"),
    ("java/lang/NegativeArraySizeException", "java/lang/RuntimeException"),
    ("java/lang/ArrayStoreException", "java/lang/RuntimeException"),
    ("java/lang/SecurityException", "java/lang/RuntimeException"),
    ("java/lang/MatchException", "java/lang/RuntimeException"),
    ("java/util/NoSuchElementException", "java/lang/RuntimeException"),
    ("java/util/ConcurrentModificationException", "java/lang/RuntimeException"),
    ("java/lang/AssertionError", "java/lang/Error"),
    ("java/lang/LinkageError", "java/lang/Error"),
    ("java/lang/NoClassDefFoundError", "java/lang/LinkageError"),
    ("java/lang/ExceptionInInitializerError", "java/lang/LinkageError"),
    ("java/lang/IncompatibleClassChangeError", "java/lang/LinkageError"),
    ("java/lang/NoSuchFieldError", "java/lang/IncompatibleClassChangeError"),
    ("java/lang/NoSuchMethodError", "java/lang/IncompatibleClassChangeError"),
    ("java/lang/AbstractMethodError", "java/lang/IncompatibleClassChangeError"),
    ("java/lang/VirtualMachineError", "java/lang/Error"),
    ("java/lang/StackOverflowError", "java/lang/VirtualMachineError"),
    ("java/lang/OutOfMemoryError", "java/lang/VirtualMachineError"),
    ("java/lang/InternalError", "java/lang/VirtualMachineError"),
    ("java/lang/Enum", "java/lang/Object"),
    ("java/lang/Record", "java/lang/Object"),
    ("java/lang/Number", "java/lang/Object"),
    ("java/lang/Integer", "java/lang/Number"),
    ("java/lang/Long", "java/lang/Number"),
    ("java/lang/Short", "java/lang/Number"),
    ("java/lang/Byte", "java/lang/Number"),
    ("java/lang/Double", "java/lang/Number"),
    ("java/lang/Float", "java/lang/Number"),
    ("java/lang/Boolean", "java/lang/Object"),
    ("java/lang/Character", "java/lang/Object"),
    ("java/lang/String", "java/lang/Object"),
    ("java/lang/AbstractStringBuilder", "java/lang/Object"),
    ("java/lang/StringBuilder", "java/lang/AbstractStringBuilder"),
    ("java/lang/Math", "java/lang/Object"),
    ("java/lang/StrictMath", "java/lang/Object"),
    ("java/lang/Class", "java/lang/Object"),
    ("java/lang/System", "java/lang/Object"),
    ("java/util/Objects", "java/lang/Object"),
    ("java/util/Optional", "java/lang/Object"),
    ("java/util/AbstractCollection", "java/lang/Object"),
    ("java/util/AbstractList", "java/util/AbstractCollection"),
    ("java/util/ArrayList", "java/util/AbstractList"),
    ("java/util/ImmutableCollections$AbstractImmutableList", "java/util/AbstractList"),
];

/// `(class or interface, direct superinterfaces)`.
const INTERFACES: &[(&str, &[&str])] = &[
    ("java/lang/Enum", &["java/lang/Comparable", "java/io/Serializable", "java/lang/constant/Constable"]),
    ("java/lang/Integer", &["java/lang/Comparable", "java/lang/constant/Constable"]),
    ("java/lang/Long", &["java/lang/Comparable", "java/lang/constant/Constable"]),
    ("java/lang/Short", &["java/lang/Comparable", "java/lang/constant/Constable"]),
    ("java/lang/Byte", &["java/lang/Comparable", "java/lang/constant/Constable"]),
    ("java/lang/Double", &["java/lang/Comparable", "java/lang/constant/Constable"]),
    ("java/lang/Float", &["java/lang/Comparable", "java/lang/constant/Constable"]),
    ("java/lang/Boolean", &["java/lang/Comparable", "java/io/Serializable", "java/lang/constant/Constable"]),
    ("java/lang/Character", &["java/lang/Comparable", "java/io/Serializable", "java/lang/constant/Constable"]),
    ("java/lang/Number", &["java/io/Serializable"]),
    ("java/lang/String", &["java/lang/CharSequence", "java/lang/Comparable", "java/io/Serializable", "java/lang/constant/Constable"]),
    ("java/lang/StringBuilder", &["java/lang/CharSequence", "java/lang/Comparable", "java/io/Serializable"]),
    ("java/lang/Throwable", &["java/io/Serializable"]),
    ("java/util/Collection", &["java/lang/Iterable"]),
    ("java/util/List", &["java/util/SequencedCollection"]),
    ("java/util/SequencedCollection", &["java/util/Collection"]),
    ("java/util/Set", &["java/util/Collection"]),
    ("java/util/SequencedSet", &["java/util/Set", "java/util/SequencedCollection"]),
    ("java/util/SortedSet", &["java/util/SequencedSet"]),
    ("java/util/AbstractCollection", &["java/util/Collection"]),
    ("java/util/AbstractList", &["java/util/List"]),
    ("java/util/ArrayList", &["java/util/List", "java/util/RandomAccess", "java/lang/Cloneable", "java/io/Serializable"]),
];

/// Classes the JDK declares `final`, for dispatch analysis.
const FINAL: &[&str] = &[
    "java/lang/String", "java/lang/Integer", "java/lang/Long", "java/lang/Short", "java/lang/Byte", "java/lang/Double",
    "java/lang/Float", "java/lang/Boolean", "java/lang/Character", "java/lang/Math", "java/lang/StrictMath",
    "java/lang/StringBuilder", "java/lang/Class", "java/lang/System", "java/util/Objects", "java/util/Optional",
];

/// Method names declared by classes whose bytecode is not read, for resolving inherited calls.
const METHODS: &[(&str, &[&str])] = &[
    ("java/lang/Object", &["<init>", "equals", "hashCode", "toString", "getClass", "clone", "finalize", "notify", "notifyAll", "wait"]),
    ("java/lang/Enum", &["<init>", "name", "ordinal", "toString", "equals", "hashCode", "clone", "compareTo", "getDeclaringClass", "describeConstable", "valueOf", "finalize"]),
    ("java/lang/Record", &["<init>", "equals", "hashCode", "toString"]),
    ("java/lang/Throwable", &["<init>", "getMessage", "getLocalizedMessage", "getCause", "initCause", "toString", "printStackTrace", "fillInStackTrace", "getStackTrace", "setStackTrace", "addSuppressed", "getSuppressed"]),
    ("java/lang/Number", &["<init>", "intValue", "longValue", "floatValue", "doubleValue", "byteValue", "shortValue"]),
    ("java/lang/AbstractStringBuilder", &["append", "length", "charAt", "toString", "reverse", "insert", "delete", "deleteCharAt", "setLength", "setCharAt", "indexOf", "lastIndexOf", "substring", "replace", "capacity", "isEmpty", "chars", "compareTo"]),
];

pub fn superclass(name: &str) -> Option<&'static str> {
    SUPERCLASSES.iter().find(|(c, _)| *c == name).map(|(_, s)| *s)
}

pub fn interfaces(name: &str) -> &'static [&'static str] {
    INTERFACES.iter().find(|(c, _)| *c == name).map(|(_, i)| *i).unwrap_or(&[])
}

pub fn is_final(name: &str) -> bool {
    FINAL.contains(&name)
}

pub fn declares(class: &str, method: &str) -> bool {
    METHODS.iter().any(|(c, methods)| *c == class && methods.contains(&method))
}

/// Whether the built-in facts know a class at all.
pub fn known(name: &str) -> bool {
    name == "java/lang/Object" || superclass(name).is_some() || INTERFACES.iter().any(|(c, _)| *c == name)
}
