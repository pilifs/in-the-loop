//! A reader for JVM class files (JVMS chapter 4): the constant pool, fields, methods, attributes and bytecode.
//!
//! The reader is complete for class files up to the Java 25 format and keeps every attribute, so that the other
//! analyses can inspect sealed hierarchies (`PermittedSubclasses`), records (`Record`), bootstrap methods
//! (`BootstrapMethods`), line numbers, parameter names and inner-class relations without a JVM.

pub mod annotations;
pub mod bytecode;
pub mod describe;
pub mod descriptor;
pub mod signature;
pub mod writer;

use std::fmt;

pub use annotations::{Annotation, ElementValue};
pub use bytecode::{ArithOp, ArrayKind, CmpOp, Cond, Insn, Kind, Narrow};
pub use describe::describe;
pub use descriptor::{MethodDescriptor, Type};

/// Access flags (JVMS 4.1, 4.5, 4.6).
pub mod flags {
    pub const PUBLIC: u16 = 0x0001;
    pub const PRIVATE: u16 = 0x0002;
    pub const PROTECTED: u16 = 0x0004;
    pub const STATIC: u16 = 0x0008;
    pub const FINAL: u16 = 0x0010;
    pub const SYNCHRONIZED: u16 = 0x0020;
    pub const SUPER: u16 = 0x0020;
    pub const VOLATILE: u16 = 0x0040;
    pub const BRIDGE: u16 = 0x0040;
    pub const TRANSIENT: u16 = 0x0080;
    pub const VARARGS: u16 = 0x0080;
    pub const NATIVE: u16 = 0x0100;
    pub const INTERFACE: u16 = 0x0200;
    pub const ABSTRACT: u16 = 0x0400;
    pub const STRICT: u16 = 0x0800;
    pub const SYNTHETIC: u16 = 0x1000;
    pub const ANNOTATION: u16 = 0x2000;
    pub const ENUM: u16 = 0x4000;
    pub const MODULE: u16 = 0x8000;
}

/// A malformed class file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ParseError(pub String);

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "malformed class file: {}", self.0)
    }
}

impl std::error::Error for ParseError {}

pub type Result<T> = std::result::Result<T, ParseError>;

fn err<T>(message: impl Into<String>) -> Result<T> {
    Err(ParseError(message.into()))
}

/// One constant pool entry (JVMS 4.4). Index 0 and the slot after a `Long` or `Double` hold `Unused`.
#[derive(Debug, Clone, PartialEq)]
pub enum Constant {
    Unused,
    Utf8(String),
    Integer(i32),
    Float(f32),
    Long(i64),
    Double(f64),
    Class { name_index: u16 },
    String { string_index: u16 },
    FieldRef { class_index: u16, name_and_type_index: u16 },
    MethodRef { class_index: u16, name_and_type_index: u16 },
    InterfaceMethodRef { class_index: u16, name_and_type_index: u16 },
    NameAndType { name_index: u16, descriptor_index: u16 },
    MethodHandle { reference_kind: u8, reference_index: u16 },
    MethodType { descriptor_index: u16 },
    Dynamic { bootstrap_method_attr_index: u16, name_and_type_index: u16 },
    InvokeDynamic { bootstrap_method_attr_index: u16, name_and_type_index: u16 },
    Module { name_index: u16 },
    Package { name_index: u16 },
}

impl Constant {
    /// The tag byte of this entry in a class file.
    pub fn tag(&self) -> u8 {
        match self {
            Constant::Unused => 0,
            Constant::Utf8(_) => 1,
            Constant::Integer(_) => 3,
            Constant::Float(_) => 4,
            Constant::Long(_) => 5,
            Constant::Double(_) => 6,
            Constant::Class { .. } => 7,
            Constant::String { .. } => 8,
            Constant::FieldRef { .. } => 9,
            Constant::MethodRef { .. } => 10,
            Constant::InterfaceMethodRef { .. } => 11,
            Constant::NameAndType { .. } => 12,
            Constant::MethodHandle { .. } => 15,
            Constant::MethodType { .. } => 16,
            Constant::Dynamic { .. } => 17,
            Constant::InvokeDynamic { .. } => 18,
            Constant::Module { .. } => 19,
            Constant::Package { .. } => 20,
        }
    }
}

/// A reference to a field or method: owner (internal name), name and descriptor.
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct MemberRef {
    pub owner: String,
    pub name: String,
    pub descriptor: String,
    /// True for an `InterfaceMethodref` entry.
    pub interface: bool,
}

impl MemberRef {
    pub fn new(owner: &str, name: &str, descriptor: &str) -> MemberRef {
        MemberRef { owner: owner.to_string(), name: name.to_string(), descriptor: descriptor.to_string(), interface: false }
    }

    /// `pkg.Owner.name`, the form the reports use.
    pub fn display(&self) -> String {
        format!("{}.{}", self.owner.replace('/', "."), self.name)
    }
}

impl fmt::Display for MemberRef {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.display())
    }
}

/// A `CONSTANT_MethodHandle`, resolved.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MethodHandle {
    /// JVMS 5.4.3.5: 1 getField, 2 getStatic, 3 putField, 4 putStatic, 5 invokeVirtual, 6 invokeStatic,
    /// 7 invokeSpecial, 8 newInvokeSpecial, 9 invokeInterface.
    pub kind: u8,
    pub member: MemberRef,
}

/// A static argument of a bootstrap method, resolved from the constant pool.
#[derive(Debug, Clone, PartialEq)]
pub enum BootstrapArg {
    Int(i32),
    Float(f32),
    Long(i64),
    Double(f64),
    Str(String),
    Class(String),
    MethodHandle(MethodHandle),
    MethodType(String),
    /// A `Dynamic` constant: an enum description for `enumSwitch`, say. Left unresolved.
    Dynamic { bootstrap_method_attr_index: u16, name: String, descriptor: String },
}

#[derive(Debug, Clone, PartialEq)]
pub struct BootstrapMethod {
    pub method: MethodHandle,
    pub args: Vec<BootstrapArg>,
}

#[derive(Debug, Clone, Default)]
pub struct ConstantPool {
    entries: Vec<Constant>,
}

impl ConstantPool {
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.len() <= 1
    }

    pub fn entries(&self) -> &[Constant] {
        &self.entries
    }

    pub fn get(&self, index: u16) -> Result<&Constant> {
        match self.entries.get(index as usize) {
            Some(Constant::Unused) | None => err(format!("constant pool index {index} out of range")),
            Some(c) => Ok(c),
        }
    }

    pub fn utf8(&self, index: u16) -> Result<&str> {
        match self.get(index)? {
            Constant::Utf8(s) => Ok(s),
            other => err(format!("constant pool index {index} is not Utf8 but tag {}", other.tag())),
        }
    }

    pub fn class_name(&self, index: u16) -> Result<&str> {
        match self.get(index)? {
            Constant::Class { name_index } => self.utf8(*name_index),
            other => err(format!("constant pool index {index} is not Class but tag {}", other.tag())),
        }
    }

    pub fn name_and_type(&self, index: u16) -> Result<(&str, &str)> {
        match self.get(index)? {
            Constant::NameAndType { name_index, descriptor_index } => {
                Ok((self.utf8(*name_index)?, self.utf8(*descriptor_index)?))
            }
            other => err(format!("constant pool index {index} is not NameAndType but tag {}", other.tag())),
        }
    }

    /// A `Fieldref`, `Methodref` or `InterfaceMethodref`.
    pub fn member(&self, index: u16) -> Result<MemberRef> {
        let (class_index, nat, interface) = match self.get(index)? {
            Constant::FieldRef { class_index, name_and_type_index } => (*class_index, *name_and_type_index, false),
            Constant::MethodRef { class_index, name_and_type_index } => (*class_index, *name_and_type_index, false),
            Constant::InterfaceMethodRef { class_index, name_and_type_index } => {
                (*class_index, *name_and_type_index, true)
            }
            other => return err(format!("constant pool index {index} is not a member reference but tag {}", other.tag())),
        };
        let (name, descriptor) = self.name_and_type(nat)?;
        Ok(MemberRef { owner: self.class_name(class_index)?.to_string(), name: name.to_string(), descriptor: descriptor.to_string(), interface })
    }

    pub fn method_handle(&self, index: u16) -> Result<MethodHandle> {
        match self.get(index)? {
            Constant::MethodHandle { reference_kind, reference_index } => {
                Ok(MethodHandle { kind: *reference_kind, member: self.member(*reference_index)? })
            }
            other => err(format!("constant pool index {index} is not MethodHandle but tag {}", other.tag())),
        }
    }

    /// The name and descriptor of an `InvokeDynamic` entry, with its bootstrap method index.
    pub fn invoke_dynamic(&self, index: u16) -> Result<(u16, &str, &str)> {
        match self.get(index)? {
            Constant::InvokeDynamic { bootstrap_method_attr_index, name_and_type_index } => {
                let (name, descriptor) = self.name_and_type(*name_and_type_index)?;
                Ok((*bootstrap_method_attr_index, name, descriptor))
            }
            other => err(format!("constant pool index {index} is not InvokeDynamic but tag {}", other.tag())),
        }
    }

    /// A loadable constant (for `ldc`), as a bootstrap argument value.
    pub fn loadable(&self, index: u16) -> Result<BootstrapArg> {
        Ok(match self.get(index)? {
            Constant::Integer(v) => BootstrapArg::Int(*v),
            Constant::Float(v) => BootstrapArg::Float(*v),
            Constant::Long(v) => BootstrapArg::Long(*v),
            Constant::Double(v) => BootstrapArg::Double(*v),
            Constant::String { string_index } => BootstrapArg::Str(self.utf8(*string_index)?.to_string()),
            Constant::Class { name_index } => BootstrapArg::Class(self.utf8(*name_index)?.to_string()),
            Constant::MethodHandle { .. } => BootstrapArg::MethodHandle(self.method_handle(index)?),
            Constant::MethodType { descriptor_index } => BootstrapArg::MethodType(self.utf8(*descriptor_index)?.to_string()),
            Constant::Dynamic { bootstrap_method_attr_index, name_and_type_index } => {
                let (name, descriptor) = self.name_and_type(*name_and_type_index)?;
                BootstrapArg::Dynamic {
                    bootstrap_method_attr_index: *bootstrap_method_attr_index,
                    name: name.to_string(),
                    descriptor: descriptor.to_string(),
                }
            }
            other => return err(format!("constant pool index {index} is not loadable (tag {})", other.tag())),
        })
    }
}

/// An attribute, kept raw; the typed accessors on [`ClassFile`], [`Method`] and [`Code`] decode the known ones.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Attribute {
    pub name: String,
    pub data: Vec<u8>,
}

#[derive(Debug, Clone)]
pub struct Field {
    pub access: u16,
    pub name: String,
    pub descriptor: String,
    pub attributes: Vec<Attribute>,
}

impl Field {
    pub fn is_static(&self) -> bool {
        self.access & flags::STATIC != 0
    }

    pub fn is_final(&self) -> bool {
        self.access & flags::FINAL != 0
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExceptionHandler {
    pub start_pc: u16,
    pub end_pc: u16,
    pub handler_pc: u16,
    /// The caught class, or `None` for `finally` (any throwable).
    pub catch_type: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LocalVariable {
    pub start_pc: u16,
    pub length: u16,
    pub name: String,
    pub descriptor: String,
    pub index: u16,
}

#[derive(Debug, Clone)]
pub struct Code {
    pub max_stack: u16,
    pub max_locals: u16,
    pub bytes: Vec<u8>,
    pub exception_table: Vec<ExceptionHandler>,
    /// `(pc, line)` pairs from every `LineNumberTable`, in order.
    pub line_numbers: Vec<(u16, u16)>,
    pub local_variables: Vec<LocalVariable>,
    pub attributes: Vec<Attribute>,
}

impl Code {
    /// The source line of the instruction at `pc`: the last line-number entry at or before it.
    pub fn line_at(&self, pc: u32) -> Option<u16> {
        let mut best: Option<(u16, u16)> = None;
        for &(start, line) in &self.line_numbers {
            if u32::from(start) <= pc && best.is_none_or(|(s, _)| start >= s) {
                best = Some((start, line));
            }
        }
        best.map(|(_, line)| line)
    }

    /// The first line of the method, from its line-number table.
    pub fn first_line(&self) -> Option<u16> {
        self.line_numbers.iter().map(|&(_, line)| line).min()
    }

    /// The decoded instructions, with the pc of each.
    pub fn instructions(&self) -> Result<Vec<(u32, Insn)>> {
        bytecode::decode(&self.bytes)
    }
}

#[derive(Debug, Clone)]
pub struct Method {
    pub access: u16,
    pub name: String,
    pub descriptor: String,
    pub code: Option<Code>,
    pub attributes: Vec<Attribute>,
}

impl Method {
    pub fn is_static(&self) -> bool {
        self.access & flags::STATIC != 0
    }

    pub fn is_native(&self) -> bool {
        self.access & flags::NATIVE != 0
    }

    pub fn is_abstract(&self) -> bool {
        self.access & flags::ABSTRACT != 0
    }

    pub fn is_synthetic(&self) -> bool {
        self.access & flags::SYNTHETIC != 0
    }

    pub fn is_bridge(&self) -> bool {
        self.access & flags::BRIDGE != 0
    }

    pub fn is_private(&self) -> bool {
        self.access & flags::PRIVATE != 0
    }

    pub fn is_final(&self) -> bool {
        self.access & flags::FINAL != 0
    }

    pub fn is_public(&self) -> bool {
        self.access & flags::PUBLIC != 0
    }

    pub fn is_protected(&self) -> bool {
        self.access & flags::PROTECTED != 0
    }

    pub fn is_constructor(&self) -> bool {
        self.name == "<init>"
    }

    pub fn is_class_initializer(&self) -> bool {
        self.name == "<clinit>"
    }

    pub fn parsed_descriptor(&self) -> Result<MethodDescriptor> {
        MethodDescriptor::parse(&self.descriptor)
    }

    /// Parameter names, from `MethodParameters` (javac `-parameters`) or else the `LocalVariableTable` (javac
    /// `-g`), or else `arg0`, `arg1`, ...
    pub fn parameter_names(&self, pool: &ConstantPool) -> Vec<String> {
        let descriptor = match self.parsed_descriptor() {
            Ok(d) => d,
            Err(_) => return Vec::new(),
        };
        let count = descriptor.params.len();
        if let Some(attr) = self.attributes.iter().find(|a| a.name == "MethodParameters") {
            if let Ok(names) = parse_method_parameters(&attr.data, pool) {
                if names.len() == count && names.iter().all(|n| !n.is_empty()) {
                    return names;
                }
            }
        }
        if let Some(code) = &self.code {
            let mut names = Vec::with_capacity(count);
            let mut slot = if self.is_static() { 0 } else { 1 };
            for param in &descriptor.params {
                let name = code
                    .local_variables
                    .iter()
                    .find(|v| v.index == slot && v.start_pc == 0)
                    .map(|v| v.name.clone());
                names.push(name);
                slot += param.slots();
            }
            if names.iter().all(|n| n.is_some()) {
                return names.into_iter().map(|n| n.unwrap_or_default()).collect();
            }
        }
        (0..count).map(|i| format!("arg{i}")).collect()
    }

    /// The first source line of the method body, when the class was compiled with line numbers.
    pub fn first_line(&self) -> Option<u16> {
        self.code.as_ref().and_then(|c| c.first_line())
    }
}

/// A component of a record class (the `Record` attribute).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RecordComponent {
    pub name: String,
    pub descriptor: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InnerClass {
    pub inner: String,
    pub outer: Option<String>,
    pub simple_name: Option<String>,
    pub access: u16,
}

/// A parsed class file.
#[derive(Debug, Clone)]
pub struct ClassFile {
    pub minor: u16,
    pub major: u16,
    pub pool: ConstantPool,
    pub access: u16,
    /// Internal name, such as `java/lang/String`.
    pub name: String,
    pub super_class: Option<String>,
    pub interfaces: Vec<String>,
    pub fields: Vec<Field>,
    pub methods: Vec<Method>,
    pub attributes: Vec<Attribute>,
}

impl ClassFile {
    /// Parses a class file.
    pub fn parse(bytes: &[u8]) -> Result<ClassFile> {
        let mut r = Reader { bytes, pos: 0 };
        if r.u32()? != 0xCAFE_BABE {
            return err("bad magic");
        }
        let minor = r.u16()?;
        let major = r.u16()?;
        let pool = read_pool(&mut r)?;
        let access = r.u16()?;
        let name = pool.class_name(r.u16()?)?.to_string();
        let super_index = r.u16()?;
        let super_class = if super_index == 0 { None } else { Some(pool.class_name(super_index)?.to_string()) };
        let interface_count = r.u16()?;
        let mut interfaces = Vec::with_capacity(interface_count as usize);
        for _ in 0..interface_count {
            interfaces.push(pool.class_name(r.u16()?)?.to_string());
        }
        let field_count = r.u16()?;
        let mut fields = Vec::with_capacity(field_count as usize);
        for _ in 0..field_count {
            let access = r.u16()?;
            let name = pool.utf8(r.u16()?)?.to_string();
            let descriptor = pool.utf8(r.u16()?)?.to_string();
            let attributes = read_attributes(&mut r, &pool)?;
            fields.push(Field { access, name, descriptor, attributes });
        }
        let method_count = r.u16()?;
        let mut methods = Vec::with_capacity(method_count as usize);
        for _ in 0..method_count {
            let access = r.u16()?;
            let name = pool.utf8(r.u16()?)?.to_string();
            let descriptor = pool.utf8(r.u16()?)?.to_string();
            let mut attributes = read_attributes(&mut r, &pool)?;
            let mut code = None;
            if let Some(i) = attributes.iter().position(|a| a.name == "Code") {
                let attr = attributes.remove(i);
                code = Some(parse_code(&attr.data, &pool)?);
            }
            methods.push(Method { access, name, descriptor, code, attributes });
        }
        let attributes = read_attributes(&mut r, &pool)?;
        if r.pos != bytes.len() {
            return err(format!("{} trailing bytes", bytes.len() - r.pos));
        }
        Ok(ClassFile { minor, major, pool, access, name, super_class, interfaces, fields, methods, attributes })
    }

    pub fn is_interface(&self) -> bool {
        self.access & flags::INTERFACE != 0
    }

    pub fn is_final(&self) -> bool {
        self.access & flags::FINAL != 0
    }

    pub fn is_abstract(&self) -> bool {
        self.access & flags::ABSTRACT != 0
    }

    pub fn is_enum(&self) -> bool {
        self.access & flags::ENUM != 0
    }

    pub fn is_record(&self) -> bool {
        self.super_class.as_deref() == Some("java/lang/Record") && self.attribute("Record").is_some()
    }

    pub fn is_sealed(&self) -> bool {
        self.attribute("PermittedSubclasses").is_some()
    }

    pub fn attribute(&self, name: &str) -> Option<&Attribute> {
        self.attributes.iter().find(|a| a.name == name)
    }

    /// The permitted direct subclasses of a sealed class, in declaration order; empty when not sealed.
    pub fn permitted_subclasses(&self) -> Result<Vec<String>> {
        match self.attribute("PermittedSubclasses") {
            None => Ok(Vec::new()),
            Some(attr) => {
                let mut r = Reader { bytes: &attr.data, pos: 0 };
                let n = r.u16()?;
                (0..n).map(|_| Ok(self.pool.class_name(r.u16()?)?.to_string())).collect()
            }
        }
    }

    /// The record components, in declaration order; empty for a class that is not a record.
    pub fn record_components(&self) -> Result<Vec<RecordComponent>> {
        match self.attribute("Record") {
            None => Ok(Vec::new()),
            Some(attr) => {
                let mut r = Reader { bytes: &attr.data, pos: 0 };
                let n = r.u16()?;
                let mut out = Vec::with_capacity(n as usize);
                for _ in 0..n {
                    let name = self.pool.utf8(r.u16()?)?.to_string();
                    let descriptor = self.pool.utf8(r.u16()?)?.to_string();
                    let _ = read_attributes(&mut r, &self.pool)?;
                    out.push(RecordComponent { name, descriptor });
                }
                Ok(out)
            }
        }
    }

    pub fn bootstrap_methods(&self) -> Result<Vec<BootstrapMethod>> {
        match self.attribute("BootstrapMethods") {
            None => Ok(Vec::new()),
            Some(attr) => {
                let mut r = Reader { bytes: &attr.data, pos: 0 };
                let n = r.u16()?;
                let mut out = Vec::with_capacity(n as usize);
                for _ in 0..n {
                    let method = self.pool.method_handle(r.u16()?)?;
                    let argc = r.u16()?;
                    let mut args = Vec::with_capacity(argc as usize);
                    for _ in 0..argc {
                        args.push(self.pool.loadable(r.u16()?)?);
                    }
                    out.push(BootstrapMethod { method, args });
                }
                Ok(out)
            }
        }
    }

    pub fn inner_classes(&self) -> Result<Vec<InnerClass>> {
        match self.attribute("InnerClasses") {
            None => Ok(Vec::new()),
            Some(attr) => {
                let mut r = Reader { bytes: &attr.data, pos: 0 };
                let n = r.u16()?;
                let mut out = Vec::with_capacity(n as usize);
                for _ in 0..n {
                    let inner = self.pool.class_name(r.u16()?)?.to_string();
                    let outer_index = r.u16()?;
                    let name_index = r.u16()?;
                    let access = r.u16()?;
                    out.push(InnerClass {
                        inner,
                        outer: if outer_index == 0 { None } else { Some(self.pool.class_name(outer_index)?.to_string()) },
                        simple_name: if name_index == 0 { None } else { Some(self.pool.utf8(name_index)?.to_string()) },
                        access,
                    });
                }
                Ok(out)
            }
        }
    }

    /// The class this one is nested in, from `InnerClasses` (or `NestHost`), if any.
    pub fn outer_class(&self) -> Option<String> {
        if let Ok(inner) = self.inner_classes() {
            if let Some(entry) = inner.iter().find(|i| i.inner == self.name) {
                if let Some(outer) = &entry.outer {
                    return Some(outer.clone());
                }
            }
        }
        if let Some(attr) = self.attribute("NestHost") {
            let mut r = Reader { bytes: &attr.data, pos: 0 };
            if let Ok(i) = r.u16() {
                if let Ok(name) = self.pool.class_name(i) {
                    return Some(name.to_string());
                }
            }
        }
        if let Some(attr) = self.attribute("EnclosingMethod") {
            let mut r = Reader { bytes: &attr.data, pos: 0 };
            if let Ok(i) = r.u16() {
                if let Ok(name) = self.pool.class_name(i) {
                    return Some(name.to_string());
                }
            }
        }
        None
    }

    /// The simple name, as `Class.getSimpleName()` returns it: `Transition` for `pkg/Decision$Transition`.
    pub fn simple_name(&self) -> String {
        if let Ok(inner) = self.inner_classes() {
            if let Some(entry) = inner.iter().find(|i| i.inner == self.name) {
                if let Some(simple) = &entry.simple_name {
                    return simple.clone();
                }
                return String::new(); // anonymous
            }
        }
        simple_name_of(&self.name)
    }

    /// The outermost class, for locating the source file: `pkg/Outer` for `pkg/Outer$Inner$Deeper`.
    pub fn source_file(&self) -> Option<String> {
        let attr = self.attribute("SourceFile")?;
        let mut r = Reader { bytes: &attr.data, pos: 0 };
        self.pool.utf8(r.u16().ok()?).ok().map(str::to_string)
    }

    pub fn method(&self, name: &str, descriptor: &str) -> Option<&Method> {
        self.methods.iter().find(|m| m.name == name && m.descriptor == descriptor)
    }

    pub fn methods_named<'a>(&'a self, name: &'a str) -> impl Iterator<Item = &'a Method> + 'a {
        self.methods.iter().filter(move |m| m.name == name)
    }

    pub fn field(&self, name: &str) -> Option<&Field> {
        self.fields.iter().find(|f| f.name == name)
    }
}

/// The simple name of an internal class name, by its last `/` and `$`: a fallback when there is no
/// `InnerClasses` attribute to consult.
pub fn simple_name_of(internal: &str) -> String {
    let base = internal.rsplit('/').next().unwrap_or(internal);
    let simple = base.rsplit('$').next().unwrap_or(base);
    simple.to_string()
}

/// `pkg.Outer` for `pkg/Outer$Inner`: the Java source file a class lives in, relative to a source root.
pub fn source_path_of(internal: &str) -> String {
    let top = match internal.find('$') {
        Some(i) => &internal[..i],
        None => internal,
    };
    format!("{top}.java")
}

struct Reader<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl Reader<'_> {
    fn u8(&mut self) -> Result<u8> {
        let b = *self.bytes.get(self.pos).ok_or_else(|| ParseError("unexpected end of class file".into()))?;
        self.pos += 1;
        Ok(b)
    }

    fn u16(&mut self) -> Result<u16> {
        Ok(u16::from_be_bytes([self.u8()?, self.u8()?]))
    }

    fn u32(&mut self) -> Result<u32> {
        Ok(u32::from_be_bytes([self.u8()?, self.u8()?, self.u8()?, self.u8()?]))
    }

    fn u64(&mut self) -> Result<u64> {
        Ok((u64::from(self.u32()?) << 32) | u64::from(self.u32()?))
    }

    fn bytes(&mut self, n: usize) -> Result<&[u8]> {
        if self.pos + n > self.bytes.len() {
            return err("unexpected end of class file");
        }
        let slice = &self.bytes[self.pos..self.pos + n];
        self.pos += n;
        Ok(slice)
    }
}

fn read_pool(r: &mut Reader) -> Result<ConstantPool> {
    let count = r.u16()? as usize;
    let mut entries = Vec::with_capacity(count);
    entries.push(Constant::Unused);
    let mut i = 1;
    while i < count {
        let tag = r.u8()?;
        let entry = match tag {
            1 => {
                let len = r.u16()? as usize;
                Constant::Utf8(decode_modified_utf8(r.bytes(len)?))
            }
            3 => Constant::Integer(r.u32()? as i32),
            4 => Constant::Float(f32::from_bits(r.u32()?)),
            5 => Constant::Long(r.u64()? as i64),
            6 => Constant::Double(f64::from_bits(r.u64()?)),
            7 => Constant::Class { name_index: r.u16()? },
            8 => Constant::String { string_index: r.u16()? },
            9 => Constant::FieldRef { class_index: r.u16()?, name_and_type_index: r.u16()? },
            10 => Constant::MethodRef { class_index: r.u16()?, name_and_type_index: r.u16()? },
            11 => Constant::InterfaceMethodRef { class_index: r.u16()?, name_and_type_index: r.u16()? },
            12 => Constant::NameAndType { name_index: r.u16()?, descriptor_index: r.u16()? },
            15 => Constant::MethodHandle { reference_kind: r.u8()?, reference_index: r.u16()? },
            16 => Constant::MethodType { descriptor_index: r.u16()? },
            17 => Constant::Dynamic { bootstrap_method_attr_index: r.u16()?, name_and_type_index: r.u16()? },
            18 => Constant::InvokeDynamic { bootstrap_method_attr_index: r.u16()?, name_and_type_index: r.u16()? },
            19 => Constant::Module { name_index: r.u16()? },
            20 => Constant::Package { name_index: r.u16()? },
            other => return err(format!("unknown constant pool tag {other} at entry {i}")),
        };
        let wide = matches!(entry, Constant::Long(_) | Constant::Double(_));
        entries.push(entry);
        i += 1;
        if wide {
            entries.push(Constant::Unused);
            i += 1;
        }
    }
    Ok(ConstantPool { entries })
}

fn read_attributes(r: &mut Reader, pool: &ConstantPool) -> Result<Vec<Attribute>> {
    let count = r.u16()?;
    let mut out = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let name = pool.utf8(r.u16()?)?.to_string();
        let len = r.u32()? as usize;
        let data = r.bytes(len)?.to_vec();
        out.push(Attribute { name, data });
    }
    Ok(out)
}

fn parse_code(data: &[u8], pool: &ConstantPool) -> Result<Code> {
    let mut r = Reader { bytes: data, pos: 0 };
    let max_stack = r.u16()?;
    let max_locals = r.u16()?;
    let len = r.u32()? as usize;
    let bytes = r.bytes(len)?.to_vec();
    let handlers = r.u16()?;
    let mut exception_table = Vec::with_capacity(handlers as usize);
    for _ in 0..handlers {
        let start_pc = r.u16()?;
        let end_pc = r.u16()?;
        let handler_pc = r.u16()?;
        let catch_index = r.u16()?;
        let catch_type = if catch_index == 0 { None } else { Some(pool.class_name(catch_index)?.to_string()) };
        exception_table.push(ExceptionHandler { start_pc, end_pc, handler_pc, catch_type });
    }
    let attributes = read_attributes(&mut r, pool)?;
    let mut line_numbers = Vec::new();
    let mut local_variables = Vec::new();
    for attr in &attributes {
        match attr.name.as_str() {
            "LineNumberTable" => {
                let mut a = Reader { bytes: &attr.data, pos: 0 };
                let n = a.u16()?;
                for _ in 0..n {
                    line_numbers.push((a.u16()?, a.u16()?));
                }
            }
            "LocalVariableTable" => {
                let mut a = Reader { bytes: &attr.data, pos: 0 };
                let n = a.u16()?;
                for _ in 0..n {
                    let start_pc = a.u16()?;
                    let length = a.u16()?;
                    let name = pool.utf8(a.u16()?)?.to_string();
                    let descriptor = pool.utf8(a.u16()?)?.to_string();
                    let index = a.u16()?;
                    local_variables.push(LocalVariable { start_pc, length, name, descriptor, index });
                }
            }
            _ => {}
        }
    }
    Ok(Code { max_stack, max_locals, bytes, exception_table, line_numbers, local_variables, attributes })
}

fn parse_method_parameters(data: &[u8], pool: &ConstantPool) -> Result<Vec<String>> {
    let mut r = Reader { bytes: data, pos: 0 };
    let n = r.u8()?;
    let mut out = Vec::with_capacity(n as usize);
    for _ in 0..n {
        let name_index = r.u16()?;
        let _access = r.u16()?;
        out.push(if name_index == 0 { String::new() } else { pool.utf8(name_index)?.to_string() });
    }
    Ok(out)
}

/// Decodes the JVM's "modified UTF-8" (JVMS 4.4.7): `C0 80` for NUL, and surrogate pairs as two 3-byte sequences.
pub fn decode_modified_utf8(bytes: &[u8]) -> String {
    let mut units: Vec<u16> = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        let b = bytes[i];
        if b & 0x80 == 0 {
            units.push(u16::from(b));
            i += 1;
        } else if b & 0xE0 == 0xC0 && i + 1 < bytes.len() {
            units.push(((u16::from(b) & 0x1F) << 6) | (u16::from(bytes[i + 1]) & 0x3F));
            i += 2;
        } else if b & 0xF0 == 0xE0 && i + 2 < bytes.len() {
            units.push(((u16::from(b) & 0x0F) << 12) | ((u16::from(bytes[i + 1]) & 0x3F) << 6) | (u16::from(bytes[i + 2]) & 0x3F));
            i += 3;
        } else {
            units.push(0xFFFD);
            i += 1;
        }
    }
    String::from_utf16_lossy(&units)
}

/// Encodes a string as modified UTF-8, the inverse of [`decode_modified_utf8`].
pub fn encode_modified_utf8(s: &str) -> Vec<u8> {
    let mut out = Vec::with_capacity(s.len());
    for unit in s.encode_utf16() {
        match unit {
            0x0001..=0x007F => out.push(unit as u8),
            0x0000 | 0x0080..=0x07FF => {
                out.push(0xC0 | ((unit >> 6) as u8 & 0x1F));
                out.push(0x80 | (unit as u8 & 0x3F));
            }
            _ => {
                out.push(0xE0 | ((unit >> 12) as u8 & 0x0F));
                out.push(0x80 | ((unit >> 6) as u8 & 0x3F));
                out.push(0x80 | (unit as u8 & 0x3F));
            }
        }
    }
    out
}

fn visible_annotations(attributes: &[Attribute], pool: &ConstantPool) -> Result<Vec<Annotation>> {
    match attributes.iter().find(|a| a.name == "RuntimeVisibleAnnotations") {
        Some(attr) => annotations::parse_annotations(&attr.data, pool),
        None => Ok(Vec::new()),
    }
}

fn signature_of(attributes: &[Attribute], pool: &ConstantPool) -> Option<String> {
    let attr = attributes.iter().find(|a| a.name == "Signature")?;
    if attr.data.len() != 2 {
        return None;
    }
    pool.utf8(u16::from_be_bytes([attr.data[0], attr.data[1]])).ok().map(str::to_string)
}

impl ClassFile {
    /// The class's annotations with `RUNTIME` retention.
    pub fn annotations(&self) -> Result<Vec<Annotation>> {
        visible_annotations(&self.attributes, &self.pool)
    }

    /// The generic signature (JVMS 4.7.9.1) of the class, when it has type parameters or generic supertypes.
    pub fn generic_signature(&self) -> Option<String> {
        signature_of(&self.attributes, &self.pool)
    }
}

impl Field {
    /// The field's annotations with `RUNTIME` retention.
    pub fn annotations(&self, pool: &ConstantPool) -> Result<Vec<Annotation>> {
        visible_annotations(&self.attributes, pool)
    }

    /// The generic signature of the field's type, when it is generic.
    pub fn generic_signature(&self, pool: &ConstantPool) -> Option<String> {
        signature_of(&self.attributes, pool)
    }
}

impl Method {
    /// The method's annotations with `RUNTIME` retention.
    pub fn annotations(&self, pool: &ConstantPool) -> Result<Vec<Annotation>> {
        visible_annotations(&self.attributes, pool)
    }

    /// The `RUNTIME` annotations of each parameter, aligned with the descriptor's parameters. The compiler leaves
    /// out the synthetic and mandated leading parameters (an inner class's outer instance, an enum constructor's
    /// name and ordinal), so a shorter list is aligned to the end.
    pub fn parameter_annotations(&self, pool: &ConstantPool) -> Result<Vec<Vec<Annotation>>> {
        let count = self.parsed_descriptor().map(|d| d.params.len()).unwrap_or(0);
        let mut lists = match self.attributes.iter().find(|a| a.name == "RuntimeVisibleParameterAnnotations") {
            Some(attr) => annotations::parse_parameter_annotations(&attr.data, pool)?,
            None => Vec::new(),
        };
        if lists.len() > count {
            lists.truncate(count);
        }
        while lists.len() < count {
            lists.insert(0, Vec::new());
        }
        Ok(lists)
    }

    /// The generic signature of the method, when it has type parameters or generic parameter or return types.
    pub fn generic_signature(&self, pool: &ConstantPool) -> Option<String> {
        signature_of(&self.attributes, pool)
    }

    /// The exception classes the method declares with `throws`, as internal names (the `Exceptions` attribute).
    pub fn declared_exceptions(&self, pool: &ConstantPool) -> Result<Vec<String>> {
        let Some(attr) = self.attributes.iter().find(|a| a.name == "Exceptions") else { return Ok(Vec::new()) };
        let mut r = Reader { bytes: &attr.data, pos: 0 };
        let count = r.u16()?;
        let mut out = Vec::with_capacity(count as usize);
        for _ in 0..count {
            out.push(pool.class_name(r.u16()?)?.to_string());
        }
        Ok(out)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn modified_utf8_round_trips() {
        for s in ["", "hello", "nul\0byte", "é ü", "日本", "😀 emoji"] {
            assert_eq!(decode_modified_utf8(&encode_modified_utf8(s)), s);
        }
        assert_eq!(encode_modified_utf8("\0"), vec![0xC0, 0x80]);
    }

    #[test]
    fn simple_names() {
        assert_eq!(simple_name_of("pkg/Decision$Transition"), "Transition");
        assert_eq!(simple_name_of("pkg/Outer"), "Outer");
        assert_eq!(source_path_of("a/b/Outer$Inner$1"), "a/b/Outer.java");
    }
}
