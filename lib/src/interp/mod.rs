//! An interpreter for the subset of the JVM that pure domain code uses, so that a behavioural contract can be
//! derived without starting a JVM.
//!
//! It executes the application's bytecode as written and models the JDK natively: strings, boxed primitives,
//! `Math`, `Objects`, immutable collections, enums, records, exceptions, string concatenation, record methods,
//! pattern-matching `switch` and lambdas. Anything outside the model stops execution with
//! [`Fault::Unsupported`], which the verifier reports as *unverifiable*: the interpreter never guesses.
//!
//! It also carries a **dynamic effect monitor**. Every heap object remembers the epoch it was allocated in, and a
//! write to an object from an earlier epoch (an argument, an enum constant, static state) stops execution with
//! [`Fault::Impure`]. Over a finite domain that is executed completely, this check is a complete proof that the
//! method has no effects on pre-existing state, which closes the gaps a static purity analysis leaves (stores into
//! arrays and collections passed in, say). Class initialisers run with the monitor relaxed, because they build the
//! very state the monitor protects.
//!
//! The interpreter has no clock, no randomness and no I/O, so every execution is deterministic by construction.

pub mod natives;
pub mod render;
pub mod value;

use std::collections::{BTreeMap, HashMap};
use std::rc::Rc;

use crate::classfile::{flags, ArithOp, ArrayKind, ClassFile, Cond, ExceptionHandler, Insn, Kind, Method, Narrow, Type};
use crate::classpath::ClassPath;

/// The longest array the interpreter allocates; a request for more is an `OutOfMemoryError`, as on a JVM whose heap
/// is smaller than the array. 2^24 elements is a 64 MB `int[]` on a JVM and 256 MB of values here.
const MAX_ARRAY_LENGTH: usize = 1 << 24;

pub use value::{Base, Heap, JStr, Native, Object, Ref, Value};

/// Why an execution stopped, other than by returning.
#[derive(Debug, Clone, PartialEq)]
pub enum Fault {
    /// A Java exception was thrown and not caught: the object.
    Throw(Ref),
    /// The code used something the interpreter does not model. The verdict is *unverifiable*.
    Unsupported(String),
    /// The effect monitor caught a write to an object that existed before the call. The method is not pure.
    Impure(String),
    /// The step or depth budget ran out: the method may not terminate on this input.
    Budget(String),
}

pub type Exec<T> = Result<T, Fault>;

/// Limits on one execution.
#[derive(Debug, Clone, Copy)]
pub struct Limits {
    /// Bytecode instructions per call of the method under test.
    pub steps: u64,
    /// Nested calls.
    pub depth: usize,
}

impl Default for Limits {
    fn default() -> Limits {
        Limits { steps: 20_000_000, depth: 2_000 }
    }
}

/// Counters over an execution, for cost reporting.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, serde::Serialize)]
pub struct Cost {
    pub steps: u64,
    pub allocations: u64,
    pub max_depth: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum InitState {
    InProgress,
    Done,
    /// Its initialization threw: a later use throws `NoClassDefFoundError` (JVMS §5.5, step 5).
    Erroneous,
}

/// Decoded bytecode of one method, cached.
struct Code {
    insns: Vec<Insn>,
    pcs: Vec<u32>,
    index: HashMap<u32, usize>,
    handlers: Vec<ExceptionHandler>,
    max_locals: usize,
}

/// The interpreter: the heap, the static state of every initialised class, and the effect monitor.
pub struct Machine<'a> {
    pub cp: &'a ClassPath,
    pub heap: Heap,
    statics: HashMap<String, BTreeMap<String, Value>>,
    init: HashMap<String, InitState>,
    interned: HashMap<String, Ref>,
    class_objects: HashMap<Type, Ref>,
    boxes: HashMap<(String, i64), Ref>,
    codes: HashMap<(String, String, String), Rc<Code>>,
    /// Whether a class has an instance field a subclass of it along its chain declares again (field hiding):
    /// only then does a field's key need the field's resolution ([`ClassPath::field_key`]).
    hides: HashMap<String, bool>,
    epoch: u32,
    clinit_depth: usize,
    pinned_in_case: bool,
    depth: usize,
    steps: u64,
    pub limits: Limits,
    pub cost: Cost,
    /// Whether the effect monitor is on. Off for class initialisation and for the replay of counterexamples.
    pub monitor: bool,
    /// The lists `List.of` and `List.copyOf` made, with the JDK class each is: its `get` out of range and its search
    /// for `null` throw as that class does, and `copyOf` hands back only these.
    immutable_lists: HashMap<Ref, ImmutableList>,
    /// The one empty list `List.of()` returns, the JDK's `ImmutableCollections.EMPTY_LIST`.
    empty_list: Option<Ref>,
}

/// The JDK class of a list `List.of` or `List.copyOf` made: `ImmutableCollections.List12` for one or two elements,
/// `ListN` for any other number.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ImmutableList {
    List12,
    ListN,
}

impl<'a> Machine<'a> {
    pub fn new(cp: &'a ClassPath) -> Machine<'a> {
        Machine {
            cp,
            heap: Heap::new(),
            statics: HashMap::new(),
            init: HashMap::new(),
            interned: HashMap::new(),
            class_objects: HashMap::new(),
            boxes: HashMap::new(),
            codes: HashMap::new(),
            hides: HashMap::new(),
            epoch: 0,
            clinit_depth: 0,
            pinned_in_case: false,
            depth: 0,
            steps: 0,
            limits: Limits::default(),
            cost: Cost::default(),
            monitor: true,
            immutable_lists: HashMap::new(),
            empty_list: None,
        }
    }

    /// Starts a new case: objects allocated from now on are the case's own, and the step budget is reset.
    /// Returns a mark for [`end_case`](Self::end_case).
    pub fn begin_case(&mut self) -> usize {
        self.epoch += 1;
        self.steps = 0;
        self.pinned_in_case = false;
        self.heap.len()
    }

    /// Reclaims the case's objects, unless global state (a class initialised, a literal interned) was allocated
    /// during it, which must stay.
    pub fn end_case(&mut self, mark: usize) {
        if !self.pinned_in_case {
            self.heap.truncate(mark);
            self.immutable_lists.retain(|r, _| (*r as usize) < mark);
        }
    }

    /// An immutable list as `List.of` makes it over `elements`, none of them `null`: the one empty list, else a new
    /// `List12` or `ListN`.
    pub(crate) fn immutable_list(&mut self, elements: Vec<Value>) -> Value {
        if elements.is_empty() {
            if let Some(r) = self.empty_list {
                return Value::Ref(r);
            }
            let saved = self.clinit_depth;
            self.clinit_depth += 1; // global state, as the JDK's constant is, not the case's own
            let r = self.alloc_native(Native::List { elements, mutable: false });
            self.clinit_depth = saved;
            self.empty_list = Some(r);
            self.immutable_lists.insert(r, ImmutableList::ListN);
            return Value::Ref(r);
        }
        let kind = if elements.len() <= 2 { ImmutableList::List12 } else { ImmutableList::ListN };
        let r = self.alloc_native(Native::List { elements, mutable: false });
        self.immutable_lists.insert(r, kind);
        Value::Ref(r)
    }

    /// The JDK class of a list `List.of` or `List.copyOf` made, if `r` is one.
    pub(crate) fn immutable_list_kind(&self, r: Ref) -> Option<ImmutableList> {
        self.immutable_lists.get(&r).copied()
    }

    pub(crate) fn alloc(&mut self, object: Object) -> Ref {
        self.cost.allocations += 1;
        // Objects made during class initialisation, interned literals, class objects and cached boxes are global
        // state: they belong to no case and must survive the end of the one that created them.
        let epoch = if self.clinit_depth > 0 {
            self.pinned_in_case = true;
            0
        } else {
            self.epoch
        };
        self.heap.alloc(object, epoch)
    }

    pub fn alloc_native(&mut self, native: Native) -> Ref {
        self.alloc(Object::Native(native))
    }

    /// A new, uninterned string object.
    pub fn new_string(&mut self, s: impl Into<JStr>) -> Value {
        Value::Ref(self.alloc(Object::Native(Native::String(s.into()))))
    }

    /// The interned string object for a literal.
    pub fn intern(&mut self, s: &str) -> Value {
        if let Some(&r) = self.interned.get(s) {
            return Value::Ref(r);
        }
        let saved = self.clinit_depth;
        self.clinit_depth += 1; // literals are global state, not the case's own
        let r = self.alloc(Object::Native(Native::String(JStr::from(s))));
        self.clinit_depth = saved;
        self.interned.insert(s.to_string(), r);
        Value::Ref(r)
    }

    /// The `Class` object for a type.
    pub fn class_object(&mut self, t: &Type) -> Value {
        if let Some(&r) = self.class_objects.get(t) {
            return Value::Ref(r);
        }
        let saved = self.clinit_depth;
        self.clinit_depth += 1;
        let r = self.alloc(Object::Native(Native::Class(t.clone())));
        self.clinit_depth = saved;
        self.class_objects.insert(t.clone(), r);
        Value::Ref(r)
    }

    /// The contents of a string object, or `None` for null or a non-string.
    pub fn units_of(&self, v: Value) -> Option<JStr> {
        match v {
            Value::Ref(r) => self.heap.string(r).cloned(),
            _ => None,
        }
    }

    /// A string object's contents for a reader ([`JStr::display`]: an isolated surrogate written `\uD800`), or
    /// `None` for null or a non-string. What a String is goes by [`Machine::units_of`].
    pub fn str_of(&self, v: Value) -> Option<String> {
        self.units_of(v).map(|s| s.display())
    }

    /// Creates a JDK exception object (not thrown).
    pub fn new_throwable(&mut self, class: &str, message: Option<&str>) -> Ref {
        let message = message.map(|m| self.new_string(m).as_ref().unwrap());
        self.alloc(Object::Native(Native::Throwable { class: class.to_string(), message, cause: None }))
    }

    /// A fault that throws a new JDK exception whose message is the string object `message`, as `new E(message)`
    /// keeps the very String it is given.
    pub fn throw_with(&mut self, class: &str, message: Option<Ref>) -> Fault {
        Fault::Throw(self.alloc(Object::Native(Native::Throwable { class: class.to_string(), message, cause: None })))
    }

    /// A fault that throws a new JDK exception with a message of these code units: one that quotes a String.
    pub fn throw_units(&mut self, class: &str, message: JStr) -> Fault {
        let message = self.new_string(message).as_ref();
        self.throw_with(class, message)
    }

    /// A fault that throws a new JDK exception.
    pub fn throw(&mut self, class: &str, message: Option<&str>) -> Fault {
        Fault::Throw(self.new_throwable(class, message))
    }

    pub fn npe(&mut self) -> Fault {
        self.throw("java/lang/NullPointerException", None)
    }

    /// The runtime class of an object, as an internal name (`[I` for arrays).
    pub fn class_of(&self, r: Ref) -> String {
        self.heap.get(r).class_name()
    }

    /// Whether an object is an instance of a class or interface, or an array type.
    pub fn is_instance(&self, r: Ref, class: &str) -> bool {
        self.cp.is_subtype(&self.class_of(r), class)
    }

    // Class initialisation

    /// Runs the static initialiser of an application class once, after its superclass's and those of its
    /// superinterfaces that declare a default method (JVMS §5.5). An exception that leaves an initialiser makes
    /// the class erroneous, and those that waited on it, and is wrapped in `ExceptionInInitializerError` unless it
    /// is an `Error`; a later use of an erroneous class throws `NoClassDefFoundError`.
    pub fn ensure_initialized(&mut self, class: &str) -> Exec<()> {
        match self.init.get(class) {
            Some(InitState::Done | InitState::InProgress) => return Ok(()),
            Some(InitState::Erroneous) => {
                let error = self.alloc(Object::Native(Native::Throwable { class: "java/lang/NoClassDefFoundError".into(), message: None, cause: None }));
                return Err(Fault::Throw(error));
            }
            None => {}
        }
        let Some(cf) = self.cp.bytecode(class).map_err(|e| Fault::Unsupported(e.to_string()))? else {
            self.init.insert(class.to_string(), InitState::Done); // JDK classes without a model have no state here
            return Ok(());
        };
        self.init.insert(class.to_string(), InitState::InProgress);
        let mut fields = BTreeMap::new();
        for field in cf.fields.iter().filter(|f| f.is_static()) {
            let t = Type::parse(&field.descriptor).map_err(|e| Fault::Unsupported(e.to_string()))?;
            let mut value = Value::default_for(&t);
            if let Some(attr) = field.attributes.iter().find(|a| a.name == "ConstantValue") {
                if attr.data.len() == 2 {
                    let index = u16::from_be_bytes([attr.data[0], attr.data[1]]);
                    value = match cf.pool.loadable(index) {
                        Ok(crate::classfile::BootstrapArg::Int(v)) => Value::Int(v),
                        Ok(crate::classfile::BootstrapArg::Long(v)) => Value::Long(v),
                        Ok(crate::classfile::BootstrapArg::Float(v)) => Value::Float(v),
                        Ok(crate::classfile::BootstrapArg::Double(v)) => Value::Double(v),
                        Ok(crate::classfile::BootstrapArg::Str(s)) => self.intern(&s),
                        _ => value,
                    };
                }
            }
            fields.insert(field.name.clone(), value);
        }
        self.statics.insert(class.to_string(), fields);
        let mut first: Vec<String> = cf.super_class.iter().cloned().collect();
        first.extend(crate::bmc::gaps::initialization_supers(self.cp, class).into_iter().filter(|i| Some(i) != cf.super_class.as_ref()));
        for s in first {
            if let Err(e) = self.ensure_initialized(&s) {
                if matches!(e, Fault::Throw(_)) {
                    self.init.insert(class.to_string(), InitState::Erroneous);
                }
                return Err(e);
            }
        }
        if let Some(clinit) = cf.method("<clinit>", "()V") {
            self.clinit_depth += 1;
            let result = self.invoke(&cf, clinit, Vec::new());
            self.clinit_depth -= 1;
            match result {
                Ok(_) => {}
                Err(Fault::Throw(exception)) => {
                    self.init.insert(class.to_string(), InitState::Erroneous);
                    if self.is_instance(exception, "java/lang/Error") {
                        return Err(Fault::Throw(exception));
                    }
                    // ExceptionInInitializerError wraps it; the class stays unusable, as on a JVM.
                    let wrapped = self.alloc(Object::Native(Native::Throwable {
                        class: "java/lang/ExceptionInInitializerError".into(),
                        message: None,
                        cause: Some(exception),
                    }));
                    return Err(Fault::Throw(wrapped));
                }
                Err(other) => return Err(other),
            }
        }
        self.init.insert(class.to_string(), InitState::Done);
        Ok(())
    }

    /// The class that declares the static field `class.name` as the JVM resolves it (JVMS §5.4.3.2): `class`, else
    /// its superinterfaces, else its superclass; `None` for a JDK class without a model.
    fn static_declarer(&self, class: &str, name: &str) -> Option<String> {
        let cf = self.cp.bytecode(class).ok()??;
        if cf.fields.iter().any(|f| f.is_static() && f.name == name) {
            return Some(class.to_string());
        }
        for i in &cf.interfaces {
            if let Some(d) = self.static_declarer(i, name) {
                return Some(d);
            }
        }
        cf.super_class.as_deref().and_then(|s| self.static_declarer(s, name))
    }

    /// Reads a static field: the class that declares it is initialised first, and only that one (JVMS §5.5).
    pub fn get_static(&mut self, class: &str, name: &str) -> Exec<Value> {
        if let Some(declaring) = self.static_declarer(class, name) {
            self.ensure_initialized(&declaring)?;
            if let Some(v) = self.statics.get(&declaring).and_then(|f| f.get(name)) {
                return Ok(*v);
            }
        }
        self.ensure_initialized(class)?;
        natives::get_static_jdk(self, class, name)
    }

    fn put_static(&mut self, class: &str, name: &str, value: Value) -> Exec<()> {
        let declaring = self.static_declarer(class, name).ok_or_else(|| Fault::Unsupported(format!("putstatic to unknown field {class}.{name}")))?;
        self.ensure_initialized(&declaring)?;
        if self.monitor && self.clinit_depth == 0 {
            return Err(Fault::Impure(format!("writes static field {}.{name}", class.replace('/', "."))));
        }
        self.statics.entry(declaring).or_default().insert(name.to_string(), value);
        Ok(())
    }

    /// The enum constants of an application enum, in declaration order.
    pub fn enum_constants(&mut self, class: &str) -> Exec<Vec<Value>> {
        self.ensure_initialized(class)?;
        let cf = self.cp.application(class).ok().flatten().ok_or_else(|| Fault::Unsupported(format!("{class} is not an application class")))?;
        let mut out = Vec::new();
        for field in cf.fields.iter().filter(|f| f.is_static() && f.access & flags::ENUM != 0) {
            if let Some(v) = self.statics.get(class).and_then(|f| f.get(&field.name)) {
                out.push(*v);
            }
        }
        Ok(out)
    }

    // Objects

    /// Allocates an instance of an application class with default field values.
    pub fn new_instance(&mut self, class: &str) -> Exec<Value> {
        self.ensure_initialized(class)?;
        let mut fields = BTreeMap::new();
        let mut base = Base::Object;
        let mut current = Some(class.to_string());
        while let Some(c) = current {
            match self.cp.bytecode(&c).map_err(|e| Fault::Unsupported(e.to_string()))? {
                Some(cf) => {
                    // A field a subclass declares again is a second field, kept under its declaring class's
                    // name ([`ClassPath::field_key`]).
                    for field in cf.fields.iter().filter(|f| !f.is_static()) {
                        let t = Type::parse(&field.descriptor).map_err(|e| Fault::Unsupported(e.to_string()))?;
                        let key = if fields.contains_key(&field.name) { format!("{c}.{}", field.name) } else { field.name.clone() };
                        fields.insert(key, Value::default_for(&t));
                    }
                    current = cf.super_class.clone();
                }
                None => {
                    if c == "java/lang/Enum" {
                        base = Base::Enum { name: String::new(), ordinal: 0, text: None };
                    } else if self.cp.is_subtype(&c, "java/lang/Throwable") {
                        base = Base::Throwable { message: None, cause: None };
                    } else if c != "java/lang/Object" && c != "java/lang/Record" {
                        return Err(Fault::Unsupported(format!("{} extends the JDK class {}, which the interpreter does not model", class.replace('/', "."), c.replace('/', "."))));
                    }
                    current = None;
                }
            }
        }
        Ok(Value::Ref(self.alloc(Object::Instance { class: class.to_string(), fields, base })))
    }

    pub fn new_array(&mut self, element: Type, length: i32) -> Exec<Value> {
        self.check_array_length(length)?;
        let data = vec![Value::default_for(&element); length as usize];
        Ok(Value::Ref(self.alloc(Object::Array { element, data })))
    }

    /// The exceptions a JVM throws for an array length before it allocates anything: `NegativeArraySizeException`,
    /// and `OutOfMemoryError` beyond what the interpreter is willing to hold. A witness replayed from JBMC may ask
    /// for `new int[Integer.MAX_VALUE]` (an index arithmetic overflow, say), which is what a JVM reports as
    /// `OutOfMemoryError: Java heap space`; without the limit the interpreter would try to allocate it.
    fn check_array_length(&mut self, length: i32) -> Exec<()> {
        if length < 0 {
            return Err(self.throw("java/lang/NegativeArraySizeException", Some(&length.to_string())));
        }
        if length as usize > MAX_ARRAY_LENGTH {
            return Err(self.throw("java/lang/OutOfMemoryError", Some("Java heap space")));
        }
        Ok(())
    }

    pub fn new_array_of(&mut self, element: Type, data: Vec<Value>) -> Value {
        Value::Ref(self.alloc(Object::Array { element, data }))
    }

    pub(crate) fn check_write(&self, target: Ref, what: &str) -> Exec<()> {
        if self.monitor && self.clinit_depth == 0 && self.heap.epoch(target) < self.epoch {
            return Err(Fault::Impure(format!("writes {what} of an object that existed before the call (a {})", self.class_of(target).replace('/', "."))));
        }
        Ok(())
    }

    /// The key the instance field `owner.name:descriptor` has in `object`: its name, unless a subclass along the
    /// object's class hides it ([`ClassPath::field_key`]).
    fn field_key(&mut self, object: Value, owner: &str, name: &str, descriptor: &str) -> Exec<String> {
        let Some(r) = object.as_ref() else { return Ok(name.to_string()) };
        let class = self.class_of(r);
        let hides = match self.hides.get(&class) {
            Some(&h) => h,
            None => {
                let h = self.cp.hides_fields(&class);
                self.hides.insert(class.clone(), h);
                h
            }
        };
        if !hides {
            return Ok(name.to_string());
        }
        let declaring = self.cp.resolve_field(owner, name, descriptor).ok_or_else(|| Fault::Unsupported(format!("no field {}.{name}", owner.replace('/', "."))))?;
        Ok(self.cp.field_key(&class, &declaring, name))
    }

    pub fn get_field(&mut self, object: Value, name: &str) -> Exec<Value> {
        let Some(r) = object.as_ref() else { return Err(self.npe()) };
        match self.heap.get(r) {
            Object::Instance { fields, .. } => fields.get(name).copied().ok_or_else(|| Fault::Unsupported(format!("no field {name} on {}", self.class_of(r)))),
            _ => Err(Fault::Unsupported(format!("getfield {name} on a {}", self.class_of(r)))),
        }
    }

    pub fn put_field(&mut self, object: Value, name: &str, value: Value) -> Exec<()> {
        let Some(r) = object.as_ref() else { return Err(self.npe()) };
        self.check_write(r, &format!("field {name}"))?;
        match self.heap.get_mut(r) {
            Object::Instance { fields, .. } => {
                fields.insert(name.to_string(), value);
                Ok(())
            }
            _ => Err(Fault::Unsupported(format!("putfield {name} on a non-instance"))),
        }
    }

    // Invocation

    fn code(&mut self, class: &ClassFile, method: &Method) -> Exec<Rc<Code>> {
        let key = (class.name.clone(), method.name.clone(), method.descriptor.clone());
        if let Some(c) = self.codes.get(&key) {
            return Ok(c.clone());
        }
        let code = method.code.as_ref().ok_or_else(|| Fault::Unsupported(format!("{}.{} has no code", class.name, method.name)))?;
        let decoded = code.instructions().map_err(|e| Fault::Unsupported(e.to_string()))?;
        let mut index = HashMap::with_capacity(decoded.len());
        let mut insns = Vec::with_capacity(decoded.len());
        let mut pcs = Vec::with_capacity(decoded.len());
        for (i, (pc, insn)) in decoded.into_iter().enumerate() {
            index.insert(pc, i);
            insns.push(insn);
            pcs.push(pc);
        }
        let compiled = Rc::new(Code { insns, pcs, index, handlers: code.exception_table.clone(), max_locals: code.max_locals as usize });
        self.codes.insert(key, compiled.clone());
        Ok(compiled)
    }

    /// Calls a static method of an application class (or a model) by name. The class is initialised first.
    pub fn call_static(&mut self, class: &str, name: &str, descriptor: &str, args: Vec<Value>) -> Exec<Option<Value>> {
        self.ensure_initialized(class)?;
        if self.cp.bytecode(class).map_err(|e| Fault::Unsupported(e.to_string()))?.is_none() {
            return Err(Fault::Unsupported(format!("class not found: {class}")));
        }
        let (owner, method) = self.cp.bytecode_method(class, name, descriptor).ok_or_else(|| Fault::Unsupported(format!("method not found: {class}.{name}{descriptor}")))?;
        self.invoke(&owner, &method, args)
    }

    /// A static call into the JDK: the model's bytecode when the tool has a model that defines the method, else
    /// the interpreter's natives. The model is the definition both engines share, so it comes first.
    fn call_static_jdk(&mut self, owner: &str, name: &str, descriptor: &str, args: Vec<Value>) -> Exec<Option<Value>> {
        if let Some((class, method)) = self.model_method(owner, name, descriptor) {
            self.ensure_initialized(owner)?;
            return self.invoke(&class, &method, args);
        }
        natives::invoke_static_jdk(self, owner, name, descriptor, args)
    }

    /// The method of a model that has code for `owner.name(descriptor)`, if the tool models the owner.
    fn model_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        self.cp.model(owner)?;
        self.cp.bytecode_method(owner, name, descriptor).filter(|(_, m)| m.code.is_some())
    }

    /// Constructs an instance of an application class: `new` followed by `<init>`.
    pub fn construct(&mut self, class: &str, descriptor: &str, args: Vec<Value>) -> Exec<Value> {
        let object = self.new_instance(class)?;
        let cf = self.cp.bytecode(class).ok().flatten().ok_or_else(|| Fault::Unsupported(format!("class not found: {class}")))?;
        let init = cf.method("<init>", descriptor).ok_or_else(|| Fault::Unsupported(format!("no constructor {class}.<init>{descriptor}")))?.clone();
        let mut full = vec![object];
        full.extend(args);
        self.invoke(&cf, &init, full)?;
        Ok(object)
    }

    /// Calls a method on a receiver with virtual dispatch (the receiver's class decides).
    pub fn call_virtual(&mut self, receiver: Value, owner: &str, name: &str, descriptor: &str, args: Vec<Value>) -> Exec<Option<Value>> {
        let Some(r) = receiver.as_ref() else { return Err(self.npe()) };
        let class = self.class_of(r);
        match self.heap.get(r) {
            Object::Instance { .. } => {
                // The most specific application (or model) implementation, else the JDK method it inherits.
                let mut current = Some(class.clone());
                while let Some(c) = current {
                    let Ok(Some(cf)) = self.cp.bytecode(&c) else { break };
                    if let Some(m) = cf.method(name, descriptor) {
                        if m.code.is_some() {
                            let m = m.clone();
                            let mut full = vec![receiver];
                            full.extend(args);
                            return self.invoke(&cf, &m, full);
                        }
                        if m.is_native() {
                            return Err(Fault::Unsupported(format!("{}.{name} is native", c.replace('/', "."))));
                        }
                    }
                    current = cf.super_class.clone();
                }
                // Default methods of application interfaces.
                for iface in self.cp.all_interfaces(&class) {
                    if let Ok(Some(cf)) = self.cp.bytecode(&iface) {
                        if let Some(m) = cf.method(name, descriptor) {
                            if m.code.is_some() {
                                let m = m.clone();
                                let mut full = vec![receiver];
                                full.extend(args);
                                return self.invoke(&cf, &m, full);
                            }
                        }
                    }
                }
                natives::invoke_inherited(self, r, owner, name, descriptor, args)
            }
            Object::Array { .. } => natives::invoke_on_array(self, r, name, descriptor, args),
            Object::Native(_) => natives::invoke_native_virtual(self, r, owner, name, descriptor, args),
        }
    }

    /// Runs a method's bytecode with the given arguments (the receiver first for instance methods).
    pub fn invoke(&mut self, class: &Rc<ClassFile>, method: &Method, args: Vec<Value>) -> Exec<Option<Value>> {
        if method.is_native() {
            return Err(Fault::Unsupported(format!("{}.{} is native", class.name.replace('/', "."), method.name)));
        }
        if method.is_abstract() {
            return Err(Fault::Unsupported(format!("{}.{} is abstract", class.name.replace('/', "."), method.name)));
        }
        self.depth += 1;
        if self.depth > self.limits.depth {
            self.depth -= 1;
            return Err(Fault::Budget(format!("calls nested deeper than {} (unbounded recursion?)", self.limits.depth)));
        }
        self.cost.max_depth = self.cost.max_depth.max(self.depth);
        let code = self.code(class, method)?;
        let mut locals = vec![Value::Int(0); code.max_locals.max(args.len() * 2)];
        let mut slot = 0;
        for arg in args {
            locals[slot] = arg;
            slot += if arg.is_wide() { 2 } else { 1 };
        }
        // Deep recursion in the interpreted code must not overflow the interpreter's own stack: grow it on demand.
        let result = stacker::maybe_grow(256 * 1024, 4 * 1024 * 1024, || self.run(class, method, &code, locals));
        self.depth -= 1;
        result
    }

    fn run(&mut self, class: &Rc<ClassFile>, method: &Method, code: &Code, mut locals: Vec<Value>) -> Exec<Option<Value>> {
        let mut stack: Vec<Value> = Vec::with_capacity(16);
        let mut i = 0usize;
        loop {
            self.steps += 1;
            self.cost.steps += 1;
            if self.steps > self.limits.steps {
                return Err(Fault::Budget(format!("more than {} bytecode steps (an unbounded loop?)", self.limits.steps)));
            }
            let insn = code.insns.get(i).ok_or_else(|| Fault::Unsupported("fell off the end of the code".into()))?;
            let pc = code.pcs[i];
            match self.step(class, method, code, insn, &mut locals, &mut stack, &mut i) {
                Ok(Flow::Next) => {}
                Ok(Flow::Return(v)) => return Ok(v),
                Err(Fault::Throw(exception)) => {
                    let thrown_class = self.class_of(exception);
                    let handler = code.handlers.iter().find(|h| {
                        u32::from(h.start_pc) <= pc
                            && pc < u32::from(h.end_pc)
                            && h.catch_type.as_deref().is_none_or(|t| self.cp.is_subtype(&thrown_class, t))
                    });
                    match handler {
                        Some(h) => {
                            stack.clear();
                            stack.push(Value::Ref(exception));
                            i = *code.index.get(&u32::from(h.handler_pc)).ok_or_else(|| Fault::Unsupported("bad handler pc".into()))?;
                        }
                        None => return Err(Fault::Throw(exception)),
                    }
                }
                Err(other) => return Err(other),
            }
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn step(&mut self, class: &Rc<ClassFile>, method: &Method, code: &Code, insn: &Insn, locals: &mut [Value], stack: &mut Vec<Value>, i: &mut usize) -> Exec<Flow> {
        macro_rules! pop {
            () => {
                stack.pop().ok_or_else(|| Fault::Unsupported("operand stack underflow".into()))?
            };
        }
        macro_rules! jump {
            ($target:expr) => {{
                *i = *code.index.get(&$target).ok_or_else(|| Fault::Unsupported("bad branch target".into()))?;
                return Ok(Flow::Next);
            }};
        }
        let pool = &class.pool;
        match insn {
            Insn::Nop => {}
            Insn::AConstNull => stack.push(Value::Null),
            Insn::IConst(v) => stack.push(Value::Int(*v)),
            Insn::LConst(v) => stack.push(Value::Long(*v)),
            Insn::FConst(v) => stack.push(Value::Float(*v)),
            Insn::DConst(v) => stack.push(Value::Double(*v)),
            Insn::Ldc(index) => {
                let v = match pool.loadable(*index).map_err(|e| Fault::Unsupported(e.to_string()))? {
                    crate::classfile::BootstrapArg::Int(v) => Value::Int(v),
                    crate::classfile::BootstrapArg::Long(v) => Value::Long(v),
                    crate::classfile::BootstrapArg::Float(v) => Value::Float(v),
                    crate::classfile::BootstrapArg::Double(v) => Value::Double(v),
                    crate::classfile::BootstrapArg::Str(s) => self.intern(&s),
                    crate::classfile::BootstrapArg::Class(name) => {
                        let t = if name.starts_with('[') { Type::parse(&name).map_err(|e| Fault::Unsupported(e.to_string()))? } else { Type::Object(name) };
                        self.class_object(&t)
                    }
                    other => return Err(Fault::Unsupported(format!("ldc of {other:?}"))),
                };
                stack.push(v);
            }
            Insn::Load(_, slot) => stack.push(locals[*slot as usize]),
            Insn::Store(_, slot) => locals[*slot as usize] = pop!(),
            Insn::ArrayLoad(kind) => {
                let index = pop!().as_int();
                let array = pop!();
                let Some(r) = array.as_ref() else { return Err(self.npe()) };
                let v = match self.heap.get(r) {
                    Object::Array { data, .. } => {
                        if index < 0 || index as usize >= data.len() {
                            let message = format!("Index {index} out of bounds for length {}", data.len());
                            return Err(self.throw("java/lang/ArrayIndexOutOfBoundsException", Some(&message)));
                        }
                        data[index as usize]
                    }
                    _ => return Err(Fault::Unsupported("array load on a non-array".into())),
                };
                let _ = kind;
                stack.push(v);
            }
            Insn::ArrayStore(kind) => {
                let value = pop!();
                let index = pop!().as_int();
                let array = pop!();
                let Some(r) = array.as_ref() else { return Err(self.npe()) };
                self.check_write(r, "an array element")?;
                if *kind == ArrayKind::Ref {
                    if let (Value::Ref(v), Object::Array { element, .. }) = (value, self.heap.get(r)) {
                        let element_class = match element {
                            Type::Object(n) => n.clone(),
                            other => other.descriptor(),
                        };
                        if !self.is_instance(v, &element_class) {
                            let message = self.class_of(v).replace('/', ".");
                            return Err(self.throw("java/lang/ArrayStoreException", Some(&message)));
                        }
                    }
                }
                match self.heap.get_mut(r) {
                    Object::Array { data, element } => {
                        if index < 0 || index as usize >= data.len() {
                            let message = format!("Index {index} out of bounds for length {}", data.len());
                            return Err(self.throw("java/lang/ArrayIndexOutOfBoundsException", Some(&message)));
                        }
                        data[index as usize] = match (element, value) {
                            (Type::Boolean, Value::Int(v)) => Value::Int(v & 1),
                            (Type::Byte, Value::Int(v)) => Value::Int(v as i8 as i32),
                            (Type::Char, Value::Int(v)) => Value::Int(v as u16 as i32),
                            (Type::Short, Value::Int(v)) => Value::Int(v as i16 as i32),
                            (_, v) => v,
                        };
                    }
                    _ => return Err(Fault::Unsupported("array store on a non-array".into())),
                }
            }
            Insn::Pop => {
                pop!();
            }
            Insn::Pop2 => {
                let v = pop!();
                if !v.is_wide() {
                    pop!();
                }
            }
            Insn::Dup => {
                let v = *stack.last().ok_or_else(|| Fault::Unsupported("stack underflow".into()))?;
                stack.push(v);
            }
            Insn::DupX1 => {
                let v1 = pop!();
                let v2 = pop!();
                stack.extend([v1, v2, v1]);
            }
            Insn::DupX2 => {
                let v1 = pop!();
                let v2 = pop!();
                if v2.is_wide() {
                    stack.extend([v1, v2, v1]);
                } else {
                    let v3 = pop!();
                    stack.extend([v1, v3, v2, v1]);
                }
            }
            Insn::Dup2 => {
                let v1 = pop!();
                if v1.is_wide() {
                    stack.extend([v1, v1]);
                } else {
                    let v2 = pop!();
                    stack.extend([v2, v1, v2, v1]);
                }
            }
            Insn::Dup2X1 => {
                let v1 = pop!();
                if v1.is_wide() {
                    let v2 = pop!();
                    stack.extend([v1, v2, v1]);
                } else {
                    let v2 = pop!();
                    let v3 = pop!();
                    stack.extend([v2, v1, v3, v2, v1]);
                }
            }
            Insn::Dup2X2 => {
                let v1 = pop!();
                if v1.is_wide() {
                    let v2 = pop!();
                    if v2.is_wide() {
                        stack.extend([v1, v2, v1]);
                    } else {
                        let v3 = pop!();
                        stack.extend([v1, v3, v2, v1]);
                    }
                } else {
                    let v2 = pop!();
                    let v3 = pop!();
                    if v3.is_wide() {
                        stack.extend([v2, v1, v3, v2, v1]);
                    } else {
                        let v4 = pop!();
                        stack.extend([v2, v1, v4, v3, v2, v1]);
                    }
                }
            }
            Insn::Swap => {
                let v1 = pop!();
                let v2 = pop!();
                stack.extend([v1, v2]);
            }
            Insn::Arith(op, kind) => {
                if *op == ArithOp::Neg {
                    let v = pop!();
                    stack.push(match v {
                        Value::Int(a) => Value::Int(a.wrapping_neg()),
                        Value::Long(a) => Value::Long(a.wrapping_neg()),
                        Value::Float(a) => Value::Float(-a),
                        Value::Double(a) => Value::Double(-a),
                        _ => return Err(Fault::Unsupported("neg of a reference".into())),
                    });
                } else {
                    let b = pop!();
                    let a = pop!();
                    stack.push(self.arith(*op, *kind, a, b)?);
                }
            }
            Insn::IInc(slot, delta) => {
                locals[*slot as usize] = Value::Int(locals[*slot as usize].as_int().wrapping_add(*delta as i32));
            }
            Insn::Convert(_, to) => {
                let v = pop!();
                stack.push(convert(v, *to));
            }
            Insn::Cmp(op) => {
                let b = pop!();
                let a = pop!();
                let r = match op.kind {
                    Kind::Long => a.as_long().cmp(&b.as_long()) as i32,
                    Kind::Float => match a.as_float().partial_cmp(&b.as_float()) {
                        Some(o) => o as i32,
                        None => op.nan,
                    },
                    Kind::Double => match a.as_double().partial_cmp(&b.as_double()) {
                        Some(o) => o as i32,
                        None => op.nan,
                    },
                    _ => return Err(Fault::Unsupported("bad cmp".into())),
                };
                stack.push(Value::Int(r));
            }
            Insn::If(cond, target) => {
                let v = pop!().as_int();
                if cond.holds(v.cmp(&0)) {
                    jump!(*target);
                }
            }
            Insn::IfICmp(cond, target) => {
                let b = pop!().as_int();
                let a = pop!().as_int();
                if cond.holds(a.cmp(&b)) {
                    jump!(*target);
                }
            }
            Insn::IfACmp(equal, target) => {
                let b = pop!();
                let a = pop!();
                let same = match (a, b) {
                    (Value::Null, Value::Null) => true,
                    (Value::Ref(x), Value::Ref(y)) => x == y,
                    _ => false,
                };
                if same == *equal {
                    jump!(*target);
                }
            }
            Insn::IfNull(target) => {
                if pop!() == Value::Null {
                    jump!(*target);
                }
            }
            Insn::IfNonNull(target) => {
                if pop!() != Value::Null {
                    jump!(*target);
                }
            }
            Insn::Goto(target) => jump!(*target),
            Insn::Jsr(_) | Insn::Ret(_) => return Err(Fault::Unsupported("jsr/ret (pre-Java 6 bytecode)".into())),
            Insn::TableSwitch { default, low, high, targets } => {
                let v = pop!().as_int();
                let target = if v >= *low && v <= *high { targets[(v - low) as usize] } else { *default };
                jump!(target);
            }
            Insn::LookupSwitch { default, pairs } => {
                let v = pop!().as_int();
                let target = pairs.iter().find(|(k, _)| *k == v).map(|(_, t)| *t).unwrap_or(*default);
                jump!(target);
            }
            Insn::Return(None) => return Ok(Flow::Return(None)),
            Insn::Return(Some(kind)) => {
                let v = pop!();
                let v = match kind {
                    Kind::Int => {
                        // Narrow to the declared return type, as the JVM does for boolean/byte/char/short.
                        let ret = method.parsed_descriptor().map(|d| d.ret).unwrap_or(Type::Int);
                        match (ret, v) {
                            (Type::Boolean, Value::Int(x)) => Value::Int(x & 1),
                            (Type::Byte, Value::Int(x)) => Value::Int(x as i8 as i32),
                            (Type::Char, Value::Int(x)) => Value::Int(x as u16 as i32),
                            (Type::Short, Value::Int(x)) => Value::Int(x as i16 as i32),
                            (_, v) => v,
                        }
                    }
                    _ => v,
                };
                return Ok(Flow::Return(Some(v)));
            }
            Insn::GetStatic(index) => {
                let field = pool.member(*index).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let v = self.get_static(&field.owner, &field.name)?;
                stack.push(v);
            }
            Insn::PutStatic(index) => {
                let field = pool.member(*index).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let v = pop!();
                self.put_static(&field.owner, &field.name, v)?;
            }
            Insn::GetField(index) => {
                let field = pool.member(*index).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let object = pop!();
                let key = self.field_key(object, &field.owner, &field.name, &field.descriptor)?;
                let v = self.get_field(object, &key)?;
                stack.push(v);
            }
            Insn::PutField(index) => {
                let field = pool.member(*index).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let v = pop!();
                let object = pop!();
                let t = Type::parse(&field.descriptor).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let v = match (t, v) {
                    (Type::Boolean, Value::Int(x)) => Value::Int(x & 1),
                    (Type::Byte, Value::Int(x)) => Value::Int(x as i8 as i32),
                    (Type::Char, Value::Int(x)) => Value::Int(x as u16 as i32),
                    (Type::Short, Value::Int(x)) => Value::Int(x as i16 as i32),
                    (_, v) => v,
                };
                let key = self.field_key(object, &field.owner, &field.name, &field.descriptor)?;
                self.put_field(object, &key, v)?;
            }
            Insn::InvokeVirtual(index) | Insn::InvokeInterface(index) => {
                let member = pool.member(*index).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let descriptor = crate::classfile::MethodDescriptor::parse(&member.descriptor).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let args = pop_args(stack, descriptor.params.len())?;
                let receiver = pop!();
                let result = self.call_virtual(receiver, &member.owner, &member.name, &member.descriptor, args)?;
                push_result(stack, result, &descriptor.ret)?;
            }
            Insn::InvokeSpecial(index) => {
                let member = pool.member(*index).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let descriptor = crate::classfile::MethodDescriptor::parse(&member.descriptor).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let args = pop_args(stack, descriptor.params.len())?;
                let receiver = pop!();
                let result = self.call_special(receiver, &member.owner, &member.name, &member.descriptor, args)?;
                push_result(stack, result, &descriptor.ret)?;
            }
            Insn::InvokeStatic(index) => {
                let member = pool.member(*index).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let descriptor = crate::classfile::MethodDescriptor::parse(&member.descriptor).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let args = pop_args(stack, descriptor.params.len())?;
                let result = if self.cp.is_application(&member.owner) {
                    self.call_static(&member.owner, &member.name, &member.descriptor, args)?
                } else {
                    self.call_static_jdk(&member.owner, &member.name, &member.descriptor, args)?
                };
                push_result(stack, result, &descriptor.ret)?;
            }
            Insn::InvokeDynamic(index) => {
                let (bootstrap_index, name, descriptor_text) = pool.invoke_dynamic(*index).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let descriptor = crate::classfile::MethodDescriptor::parse(descriptor_text).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let args = pop_args(stack, descriptor.params.len())?;
                let result = natives::invoke_dynamic(self, class, bootstrap_index, name, &descriptor, args)?;
                push_result(stack, result, &descriptor.ret)?;
            }
            Insn::New(index) => {
                let name = pool.class_name(*index).map_err(|e| Fault::Unsupported(e.to_string()))?.to_string();
                let v = if self.cp.has_bytecode(&name) { self.new_instance(&name)? } else { natives::new_jdk_object(self, &name)? };
                stack.push(v);
            }
            Insn::NewArray(kind) => {
                let length = pop!().as_int();
                let element = match kind {
                    ArrayKind::Int => Type::Int,
                    ArrayKind::Long => Type::Long,
                    ArrayKind::Float => Type::Float,
                    ArrayKind::Double => Type::Double,
                    ArrayKind::Byte => Type::Byte,
                    ArrayKind::Char => Type::Char,
                    ArrayKind::Short => Type::Short,
                    ArrayKind::Ref => Type::object("java/lang/Object"),
                };
                let v = self.new_array(element, length)?;
                stack.push(v);
            }
            Insn::ANewArray(index) => {
                let length = pop!().as_int();
                let name = pool.class_name(*index).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let element = if name.starts_with('[') { Type::parse(name).map_err(|e| Fault::Unsupported(e.to_string()))? } else { Type::Object(name.to_string()) };
                let v = self.new_array(element, length)?;
                stack.push(v);
            }
            Insn::MultiANewArray(index, dims) => {
                let name = pool.class_name(*index).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let t = Type::parse(name).map_err(|e| Fault::Unsupported(e.to_string()))?;
                let mut sizes = Vec::new();
                for _ in 0..*dims {
                    sizes.push(pop!().as_int());
                }
                sizes.reverse();
                let v = self.multi_array(&t, &sizes)?;
                stack.push(v);
            }
            Insn::ArrayLength => {
                let Some(r) = pop!().as_ref() else { return Err(self.npe()) };
                match self.heap.get(r) {
                    Object::Array { data, .. } => stack.push(Value::Int(data.len() as i32)),
                    _ => return Err(Fault::Unsupported("arraylength of a non-array".into())),
                }
            }
            Insn::AThrow => {
                let Some(r) = pop!().as_ref() else { return Err(self.npe()) };
                return Err(Fault::Throw(r));
            }
            Insn::CheckCast(index) => {
                let name = pool.class_name(*index).map_err(|e| Fault::Unsupported(e.to_string()))?.to_string();
                let v = *stack.last().ok_or_else(|| Fault::Unsupported("stack underflow".into()))?;
                if let Value::Ref(r) = v {
                    if !self.is_instance(r, &name) {
                        let message = format!("class {} cannot be cast to class {}", self.class_of(r).replace('/', "."), name.replace('/', "."));
                        return Err(self.throw("java/lang/ClassCastException", Some(&message)));
                    }
                }
            }
            Insn::InstanceOf(index) => {
                let name = pool.class_name(*index).map_err(|e| Fault::Unsupported(e.to_string()))?.to_string();
                let v = pop!();
                let result = match v {
                    Value::Ref(r) => self.is_instance(r, &name),
                    _ => false,
                };
                stack.push(Value::bool(result));
            }
            Insn::MonitorEnter | Insn::MonitorExit => {
                if pop!() == Value::Null {
                    return Err(self.npe());
                }
            }
        }
        *i += 1;
        Ok(Flow::Next)
    }

    fn multi_array(&mut self, t: &Type, sizes: &[i32]) -> Exec<Value> {
        let Type::Array(element) = t else { return Err(Fault::Unsupported("multianewarray of a non-array type".into())) };
        if sizes.len() == 1 {
            return self.new_array((**element).clone(), sizes[0]);
        }
        self.check_array_length(sizes[0])?;
        let mut data = Vec::with_capacity(sizes[0] as usize);
        for _ in 0..sizes[0] {
            data.push(self.multi_array(element, &sizes[1..])?);
        }
        Ok(self.new_array_of((**element).clone(), data))
    }

    /// `invokespecial`: constructors, private methods and `super.` calls go to the named class, not the receiver's.
    fn call_special(&mut self, receiver: Value, owner: &str, name: &str, descriptor: &str, args: Vec<Value>) -> Exec<Option<Value>> {
        let Some(r) = receiver.as_ref() else { return Err(self.npe()) };
        if let Ok(Some(_)) = self.cp.bytecode(owner) {
            if let Some((cf, m)) = self.cp.bytecode_method(owner, name, descriptor) {
                if m.code.is_some() {
                    let mut full = vec![receiver];
                    full.extend(args);
                    return self.invoke(&cf, &m, full);
                }
                if !m.is_abstract() {
                    return Err(Fault::Unsupported(format!("{}.{name} has no code", owner.replace('/', "."))));
                }
            }
            // Inherited from the JDK (e.g. Enum.<init> called through the enum's own class).
            return natives::invoke_inherited(self, r, owner, name, descriptor, args);
        }
        natives::invoke_special_jdk(self, r, owner, name, descriptor, args)
    }

    fn arith(&mut self, op: ArithOp, kind: Kind, a: Value, b: Value) -> Exec<Value> {
        Ok(match kind {
            Kind::Int => {
                let (x, y) = (a.as_int(), b.as_int());
                Value::Int(match op {
                    ArithOp::Add => x.wrapping_add(y),
                    ArithOp::Sub => x.wrapping_sub(y),
                    ArithOp::Mul => x.wrapping_mul(y),
                    ArithOp::Div => {
                        if y == 0 {
                            return Err(self.throw("java/lang/ArithmeticException", Some("/ by zero")));
                        }
                        x.wrapping_div(y)
                    }
                    ArithOp::Rem => {
                        if y == 0 {
                            return Err(self.throw("java/lang/ArithmeticException", Some("/ by zero")));
                        }
                        x.wrapping_rem(y)
                    }
                    ArithOp::Shl => x.wrapping_shl(y as u32 & 0x1f),
                    ArithOp::Shr => x.wrapping_shr(y as u32 & 0x1f),
                    ArithOp::Ushr => ((x as u32).wrapping_shr(y as u32 & 0x1f)) as i32,
                    ArithOp::And => x & y,
                    ArithOp::Or => x | y,
                    ArithOp::Xor => x ^ y,
                    ArithOp::Neg => unreachable!(),
                })
            }
            Kind::Long => {
                let x = a.as_long();
                Value::Long(match op {
                    ArithOp::Shl => x.wrapping_shl(b.as_int() as u32 & 0x3f),
                    ArithOp::Shr => x.wrapping_shr(b.as_int() as u32 & 0x3f),
                    ArithOp::Ushr => ((x as u64).wrapping_shr(b.as_int() as u32 & 0x3f)) as i64,
                    _ => {
                        let y = b.as_long();
                        match op {
                            ArithOp::Add => x.wrapping_add(y),
                            ArithOp::Sub => x.wrapping_sub(y),
                            ArithOp::Mul => x.wrapping_mul(y),
                            ArithOp::Div => {
                                if y == 0 {
                                    return Err(self.throw("java/lang/ArithmeticException", Some("/ by zero")));
                                }
                                x.wrapping_div(y)
                            }
                            ArithOp::Rem => {
                                if y == 0 {
                                    return Err(self.throw("java/lang/ArithmeticException", Some("/ by zero")));
                                }
                                x.wrapping_rem(y)
                            }
                            ArithOp::And => x & y,
                            ArithOp::Or => x | y,
                            ArithOp::Xor => x ^ y,
                            _ => unreachable!(),
                        }
                    }
                })
            }
            Kind::Float => {
                let (x, y) = (a.as_float(), b.as_float());
                Value::Float(match op {
                    ArithOp::Add => x + y,
                    ArithOp::Sub => x - y,
                    ArithOp::Mul => x * y,
                    ArithOp::Div => x / y,
                    ArithOp::Rem => x % y,
                    _ => return Err(Fault::Unsupported("bitwise op on float".into())),
                })
            }
            Kind::Double => {
                let (x, y) = (a.as_double(), b.as_double());
                Value::Double(match op {
                    ArithOp::Add => x + y,
                    ArithOp::Sub => x - y,
                    ArithOp::Mul => x * y,
                    ArithOp::Div => x / y,
                    ArithOp::Rem => x % y,
                    _ => return Err(Fault::Unsupported("bitwise op on double".into())),
                })
            }
            Kind::Ref => return Err(Fault::Unsupported("arithmetic on references".into())),
        })
    }
}

enum Flow {
    Next,
    Return(Option<Value>),
}

fn convert(v: Value, to: Narrow) -> Value {
    match to {
        Narrow::Byte => Value::Int(v.as_int() as i8 as i32),
        Narrow::Char => Value::Int(v.as_int() as u16 as i32),
        Narrow::Short => Value::Int(v.as_int() as i16 as i32),
        Narrow::To(kind) => {
            let as_f64 = match v {
                Value::Int(x) => x as f64,
                Value::Long(x) => x as f64,
                Value::Float(x) => x as f64,
                Value::Double(x) => x,
                _ => 0.0,
            };
            match (v, kind) {
                (Value::Int(x), Kind::Long) => Value::Long(x as i64),
                (Value::Int(x), Kind::Float) => Value::Float(x as f32),
                (Value::Int(x), Kind::Double) => Value::Double(x as f64),
                (Value::Long(x), Kind::Int) => Value::Int(x as i32),
                (Value::Long(x), Kind::Float) => Value::Float(x as f32),
                (Value::Long(x), Kind::Double) => Value::Double(x as f64),
                (Value::Float(x), Kind::Int) => Value::Int(x as i32), // saturating, NaN to 0: the JVM's rule
                (Value::Float(x), Kind::Long) => Value::Long(x as i64),
                (Value::Float(x), Kind::Double) => Value::Double(x as f64),
                (Value::Double(_), Kind::Int) => Value::Int(as_f64 as i32),
                (Value::Double(_), Kind::Long) => Value::Long(as_f64 as i64),
                (Value::Double(_), Kind::Float) => Value::Float(as_f64 as f32),
                (v, _) => v,
            }
        }
    }
}

fn pop_args(stack: &mut Vec<Value>, count: usize) -> Exec<Vec<Value>> {
    if stack.len() < count {
        return Err(Fault::Unsupported("operand stack underflow at call".into()));
    }
    Ok(stack.split_off(stack.len() - count))
}

fn push_result(stack: &mut Vec<Value>, result: Option<Value>, ret: &Type) -> Exec<()> {
    match (ret, result) {
        (Type::Void, _) => Ok(()),
        (_, Some(v)) => {
            stack.push(v);
            Ok(())
        }
        (_, None) => Err(Fault::Unsupported("a non-void method returned nothing".into())),
    }
}

/// `if<cond>` semantics exposed for the harness expression evaluator.
pub fn cond_holds(cond: Cond, a: i64, b: i64) -> bool {
    cond.holds(a.cmp(&b))
}
