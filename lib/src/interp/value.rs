//! Values and heap objects of the interpreter.

use std::collections::BTreeMap;

use crate::classfile::Type;

/// A reference to a heap object: an index into [`Heap`](super::Heap).
pub type Ref = u32;

/// A JVM value on the operand stack or in a local variable. Booleans, bytes, chars and shorts are ints.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Value {
    Int(i32),
    Long(i64),
    Float(f32),
    Double(f64),
    Null,
    Ref(Ref),
}

impl Value {
    pub fn as_int(self) -> i32 {
        match self {
            Value::Int(v) => v,
            other => panic!("expected int, found {other:?}"),
        }
    }

    pub fn as_long(self) -> i64 {
        match self {
            Value::Long(v) => v,
            other => panic!("expected long, found {other:?}"),
        }
    }

    pub fn as_float(self) -> f32 {
        match self {
            Value::Float(v) => v,
            other => panic!("expected float, found {other:?}"),
        }
    }

    pub fn as_double(self) -> f64 {
        match self {
            Value::Double(v) => v,
            other => panic!("expected double, found {other:?}"),
        }
    }

    pub fn as_ref(self) -> Option<Ref> {
        match self {
            Value::Ref(r) => Some(r),
            Value::Null => None,
            other => panic!("expected reference, found {other:?}"),
        }
    }

    pub fn is_wide(self) -> bool {
        matches!(self, Value::Long(_) | Value::Double(_))
    }

    /// The default value of a field or array element of this type.
    pub fn default_for(t: &Type) -> Value {
        match t {
            Type::Long => Value::Long(0),
            Type::Float => Value::Float(0.0),
            Type::Double => Value::Double(0.0),
            Type::Object(_) | Type::Array(_) => Value::Null,
            _ => Value::Int(0),
        }
    }

    pub fn bool(b: bool) -> Value {
        Value::Int(b as i32)
    }
}

/// The state inherited from a JDK superclass that has no bytecode in the interpreter: `Enum`'s name and ordinal,
/// `Throwable`'s message and cause.
#[derive(Debug, Clone, PartialEq)]
pub enum Base {
    Object,
    /// `text` is the `String` object the constructor was given, which `name()` returns, so that two calls give one
    /// object as on a JVM; `None` before the constructor runs.
    Enum { name: String, ordinal: i32, text: Option<Ref> },
    Throwable { message: Option<Ref>, cause: Option<Ref> },
}

/// An object modelled natively, standing in for a JDK class whose bytecode is not run.
#[derive(Debug, Clone, PartialEq)]
pub enum Native {
    /// `java.lang.String`.
    String(String),
    /// An immutable `java.util.List` from `List.of`/`List.copyOf`, or an `ArrayList`.
    List { elements: Vec<Value>, mutable: bool },
    /// `java.util.Set` from `Set.of`, or a `HashSet`/`LinkedHashSet` (insertion-ordered).
    Set { elements: Vec<Value>, mutable: bool },
    /// `java.util.Map` from `Map.of`, or a `HashMap`/`LinkedHashMap`: insertion-ordered pairs.
    Map { entries: Vec<(Value, Value)>, mutable: bool },
    /// `java.lang.StringBuilder`.
    StringBuilder(String),
    /// A boxed primitive: `Integer`, `Long`, `Boolean`, ...: the class name and the value.
    Boxed { class: String, value: Value },
    /// `java.lang.Class`, by the type it denotes.
    Class(Type),
    /// An iterator over a snapshot of a list or set.
    Iterator { elements: Vec<Value>, position: usize },
    /// An exception of a JDK class: `java.lang.ArithmeticException`, say.
    Throwable { class: String, message: Option<Ref>, cause: Option<Ref> },
    /// A lambda or method reference: the functional interface and its method, the implementation method and the
    /// captured arguments, and the instantiated method type (for boxing adaptations).
    Lambda { interface: String, sam_name: String, implementation: crate::classfile::MethodHandle, captured: Vec<Value>, instantiated: String },
    /// `java.util.Optional`.
    Optional(Option<Value>),
}

/// A heap object.
#[derive(Debug, Clone, PartialEq)]
pub enum Object {
    /// An instance of an application class.
    Instance { class: String, fields: BTreeMap<String, Value>, base: Base },
    /// An array, with its element type.
    Array { element: Type, data: Vec<Value> },
    Native(Native),
}

impl Object {
    /// The class name a JVM would report for this object: `pkg/Decision$Transition`, `[I`, `java/lang/String`.
    pub fn class_name(&self) -> String {
        match self {
            Object::Instance { class, .. } => class.clone(),
            Object::Array { element, .. } => format!("[{}", element.descriptor()),
            Object::Native(n) => n.class_name().to_string(),
        }
    }
}

impl Native {
    pub fn class_name(&self) -> &str {
        match self {
            Native::String(_) => "java/lang/String",
            Native::List { mutable: false, .. } => "java/util/ImmutableCollections$ListN",
            Native::List { mutable: true, .. } => "java/util/ArrayList",
            Native::Set { mutable: false, .. } => "java/util/ImmutableCollections$SetN",
            Native::Set { mutable: true, .. } => "java/util/LinkedHashSet",
            Native::Map { mutable: false, .. } => "java/util/ImmutableCollections$MapN",
            Native::Map { mutable: true, .. } => "java/util/LinkedHashMap",
            Native::StringBuilder(_) => "java/lang/StringBuilder",
            Native::Boxed { class, .. } => class,
            Native::Class(_) => "java/lang/Class",
            Native::Iterator { .. } => "java/util/Iterator",
            Native::Throwable { class, .. } => class,
            Native::Lambda { interface, .. } => interface,
            Native::Optional(_) => "java/util/Optional",
        }
    }
}

/// The heap: every object ever allocated, with the epoch it was allocated in, for the effect monitor.
#[derive(Debug, Default)]
pub struct Heap {
    objects: Vec<Object>,
    epochs: Vec<u32>,
}

impl Heap {
    pub fn new() -> Heap {
        Heap::default()
    }

    pub fn alloc(&mut self, object: Object, epoch: u32) -> Ref {
        self.objects.push(object);
        self.epochs.push(epoch);
        (self.objects.len() - 1) as Ref
    }

    pub fn get(&self, r: Ref) -> &Object {
        &self.objects[r as usize]
    }

    pub fn get_mut(&mut self, r: Ref) -> &mut Object {
        &mut self.objects[r as usize]
    }

    pub fn epoch(&self, r: Ref) -> u32 {
        self.epochs[r as usize]
    }

    pub fn len(&self) -> usize {
        self.objects.len()
    }

    pub fn is_empty(&self) -> bool {
        self.objects.is_empty()
    }

    /// Forgets every object allocated at or after `len`, after a case has been rendered.
    pub fn truncate(&mut self, len: usize) {
        self.objects.truncate(len);
        self.epochs.truncate(len);
    }

    pub fn string(&self, r: Ref) -> Option<&str> {
        match self.get(r) {
            Object::Native(Native::String(s)) => Some(s),
            _ => None,
        }
    }
}
