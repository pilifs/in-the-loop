//! R2's first part: the read footprint of a read-only heap helper, proved from its bytecode, and the helper lifted
//! over it, the explicit representation adapter its own proof and a caller's reuse stand on.
//!
//! **The category** is the brief's one conservative one: an instance method of an application class, deterministic
//! and read-only, over primitive fields of its receiver, one-dimensional primitive arrays its receiver's fields hold,
//! and primitive arguments, with a primitive result. [`footprint`] establishes it from the bytecode, and refuses by
//! name what it doesn't establish:
//!
//! | Refused | Why |
//! |---|---|
//! | a write of a field or a static, an allocation, an exception it throws, a monitor | not read-only, or not total |
//! | a static field read, a call into the JDK beyond its arithmetic classes, an interface or dynamic call | state or code outside its footprint |
//! | a call of a method on an object (its receiver's included), a class that overrides it | dispatch that the class path doesn't fix |
//! | recursion, through static callees too | its proof would need an unbounded unwinding |
//! | a reference other than the receiver and the arrays its fields hold: a reference parameter, field, constant or `null`, a cast, a reference test | an escaping or aliased reference |
//! | an array used other than by its length and its elements' reads (written, passed on, returned, compared), an array of references, floating point or arrays, an array allocated | not read-only, or an escaping reference |
//! | a division or remainder by anything but a non-zero constant | it may throw: not total |
//! | `float` and `double` | outside this wave |
//!
//! **Why the footprint is proved, not listed.** A method accepted here has only primitive parameters, and the only
//! instruction it has that yields a reference is a load of local 0 that a `getfield` consumes at once, with no branch
//! into the pair; it never stores to local 0. So every reference it ever handles is its receiver, every field it
//! reads is a field of its receiver, and the `getfield`s are all its reads of the heap: the static callees it reaches
//! are accepted under the same rules with no reference at all. It writes nothing, so a field holds the same value at
//! every read during one call, the value it held at the call. Its outcome is therefore a function of the values of
//! the fields it reads and of its arguments, and nothing else of the receiver or the heap can change it. It throws
//! nothing: no instruction it has can throw on a receiver that isn't `null` (a call on `null` throws before it runs).
//!
//! **Arrays** (the brief's bounded reads of primitive arrays, after the field-only case). A field holding a
//! one-dimensional array of a non-floating primitive type may be read too, and its array read by its length and its
//! elements. A flow of the helper's own code (over every path, its locals included) shows that every
//! reference it handles is its receiver or an array one of those fields held: an array is stored only in a local
//! other than the receiver's, and used only by `arraylength` and an element load of its own type. No instruction
//! writes an array, so the array's length and elements hold the same values at every read during one call, the
//! values they held at the call, and the outcome is a function of those and of the other values above. A read out
//! of bounds throws the JVM's `ArrayIndexOutOfBoundsException`, so a helper reading arrays is not total: that
//! exception is an outcome like a result, and the summary's proof compares it. A static callee still handles no
//! reference.
//!
//! **The lifted helper** ([`lift`]) is that function: a static method of a class of its own, in the helper's package,
//! whose parameters are the helper's, then the values of the fields it reads, in the order given (an array field's
//! value is the array). Its code is the helper's, with each `aload_0; getfield` pair replaced by a load of the field's
//! parameter and every other local moved past them. Lifted over the same fields in both versions (their union), the two versions' lifted helpers have
//! one signature, and a regression proof of them is a proof that the helper's two versions have the same outcome on
//! every receiver whose read fields hold the same values, given the same arguments, whatever else the receivers hold.

use std::collections::{HashMap, HashSet};

use serde::Serialize;

use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};
use crate::classfile::bytecode::ArrayKind;
use crate::classfile::{flags, ArithOp, BootstrapArg, ClassFile, Insn, Kind, MemberRef, Method, MethodDescriptor, Narrow, Type};
use crate::classpath::ClassPath;
use crate::spec::{Part, Unsupported};

/// The suffix of a lifted helper's class: `quotes/QuoteService$Footprint$fee`.
pub const LIFTED: &str = "$Footprint$";

/// A field of the receiver a helper reads.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
pub struct FieldRead {
    pub name: String,
    pub descriptor: String,
    /// The class that declares it, by internal name.
    pub declared_by: String,
}

impl FieldRead {
    pub fn ty(&self) -> Type {
        Type::parse(&self.descriptor).expect("a field read was checked to have a primitive type, or to be an array of one")
    }

    /// Whether it holds an array, of a primitive type.
    pub fn is_array(&self) -> bool {
        self.descriptor.starts_with('[')
    }
}

/// What [`footprint`] established of a helper.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Footprint {
    /// The helper, as its class declares it.
    pub helper: MemberRef,
    pub params: Vec<Type>,
    pub result: Type,
    /// Every field of its receiver it reads, by name: all it reads of the heap.
    pub fields: Vec<FieldRead>,
    /// The static methods it reaches, as declared, each accepted under the same rules with no reference at all.
    pub calls: Vec<MemberRef>,
    /// Whether it is private: a call of it is an `invokespecial`.
    pub private: bool,
}

impl Footprint {
    /// `["this.feeCents", "arg0"]`: the footprint as a summary names it.
    pub fn reads(fields: &[FieldRead], params: &[Type]) -> Vec<String> {
        fields.iter().map(|f| format!("this.{}", f.name)).chain((0..params.len()).map(|i| format!("arg{i}"))).collect()
    }
}

/// `quotes.QuoteService#fee(I)J`, a helper as a summary names it.
pub fn helper_name(m: &MemberRef) -> String {
    format!("{}#{}{}", m.owner.replace('/', "."), m.name, m.descriptor)
}

fn refused(helper: &MemberRef, why: impl std::fmt::Display) -> Unsupported {
    Unsupported::new(Part::Reuse, format!("{} has no read-only summary: {why}", helper_name(helper)))
}

/// The read footprint of `helper` (an instance method, as a call names it) on `cp`, which needs the JDK, or why it
/// is not of the category this module establishes (see the module's documentation).
pub fn footprint(cp: &ClassPath, helper: &MemberRef) -> Result<Footprint, Unsupported> {
    let Some((class, method)) = cp.find_method(&helper.owner, &helper.name, &helper.descriptor) else { return Err(refused(helper, "the class path has no such method")) };
    let declared = MemberRef::new(&class.name, &helper.name, &helper.descriptor);
    let refuse = |why: String| refused(&declared, why);
    if !cp.is_application(&class.name) {
        return Err(refuse("it is not the application's".into()));
    }
    if class.is_interface() {
        return Err(refuse("it is an interface's".into()));
    }
    if method.is_static() {
        return Err(refuse("it is static: a pure static helper is shared as one function already".into()));
    }
    if method.is_native() || method.is_abstract() {
        return Err(refuse("it has no bytecode".into()));
    }
    if method.access & flags::SYNCHRONIZED != 0 {
        return Err(refuse("it synchronizes on its receiver".into()));
    }
    let descriptor = method.parsed_descriptor().map_err(|e| refuse(e.to_string()))?;
    signature(&descriptor).map_err(&refuse)?;
    if !(method.is_private() || method.is_final() || cp.is_effectively_final(&class.name)) {
        let classes = cp.application_classes().map_err(|e| refuse(e.to_string()))?;
        if let Some(other) = classes.iter().find(|(name, c)| **name != class.name && cp.is_subtype(name, &class.name) && c.method(&helper.name, &helper.descriptor).is_some_and(|m| !m.is_static() && !m.is_private())) {
            return Err(refuse(format!("{} overrides it, so the class path doesn't fix the method a call runs", other.0.replace('/', "."))));
        }
    }
    let mut walk = Walk { cp, fields: Vec::new(), calls: Vec::new(), open: vec![declared.clone()], receiver: class.name.clone() };
    walk.method(&class, &method, true).map_err(&refuse)?;
    let mut fields = walk.fields;
    fields.sort();
    fields.dedup();
    Ok(Footprint { helper: declared, params: descriptor.params, result: descriptor.ret, fields, calls: walk.calls, private: method.is_private() })
}

/// Primitive parameters and a primitive result, none of them floating point.
fn signature(d: &MethodDescriptor) -> Result<(), String> {
    if let Some(p) = d.params.iter().find(|t| !t.is_primitive()) {
        return Err(format!("it takes a {}: only primitive arguments, and its receiver's fields, are read", p.java_name()));
    }
    if !d.ret.is_primitive() || d.ret == Type::Void {
        return Err(format!("it returns {}: only a primitive result is summarized", if d.ret == Type::Void { "nothing".to_string() } else { format!("a {}", d.ret.java_name()) }));
    }
    if d.params.iter().chain([&d.ret]).any(|t| matches!(t, Type::Float | Type::Double)) {
        return Err("it has a floating-point parameter or result, outside this wave".into());
    }
    Ok(())
}

struct Walk<'a> {
    cp: &'a ClassPath,
    fields: Vec<FieldRead>,
    calls: Vec<MemberRef>,
    /// The methods being walked, innermost last: a call of one is recursion.
    open: Vec<MemberRef>,
    /// The class declaring the helper.
    receiver: String,
}

impl Walk<'_> {
    /// Checks one method's code: the helper's own (`root`, with its receiver in local 0) or a static callee's.
    fn method(&mut self, class: &ClassFile, method: &Method, root: bool) -> Result<(), String> {
        let code = method.code.as_ref().ok_or("it has no code")?;
        if !code.exception_table.is_empty() {
            return Err(format!("{} has an exception handler", where_(class, method, root)));
        }
        let insns = code.instructions().map_err(|e| e.to_string())?;
        let targets: HashSet<u32> = insns.iter().flat_map(|(_, i)| i.targets()).collect();
        let pool = &class.pool;
        let at = |what: &str| format!("{} {what}", where_(class, method, root));
        // A use of the receiver other than a field read is reported once nothing more telling is found: a write
        // through it, or a call it is passed to, names what the helper does.
        let mut misuse = None;
        let mut i = 0;
        while i < insns.len() {
            let (offset, insn) = &insns[i];
            match insn {
                Insn::Load(Kind::Ref, 0) if root => {
                    let Some((next_at, Insn::GetField(f))) = insns.get(i + 1) else {
                        misuse.get_or_insert_with(|| at("uses its receiver other than to read one of its fields"));
                        i += 1;
                        continue;
                    };
                    if targets.contains(next_at) {
                        misuse.get_or_insert_with(|| at("branches between loading its receiver and reading its field"));
                        i += 1;
                        continue;
                    }
                    let field = pool.member(*f).map_err(|e| e.to_string())?;
                    self.field(&field).map_err(|e| at(&e))?;
                    i += 2;
                    continue;
                }
                // An array a field of the receiver holds, kept in a local: what the flow below follows.
                Insn::Load(Kind::Ref, s) | Insn::Store(Kind::Ref, s) if root && *s != 0 => {}
                Insn::Load(Kind::Ref, _) | Insn::Store(Kind::Ref, _) | Insn::AConstNull => return Err(at("handles a reference other than its receiver")),
                Insn::Load(Kind::Float | Kind::Double, _) | Insn::Store(Kind::Float | Kind::Double, _) | Insn::FConst(_) | Insn::DConst(_) => return Err(at("computes in floating point, outside this wave")),
                Insn::Load(_, 0) | Insn::Store(_, 0) | Insn::IInc(0, _) if root => return Err(at("reuses its receiver's local")),
                Insn::Load(..) | Insn::Store(..) | Insn::IInc(..) | Insn::IConst(_) | Insn::LConst(_) | Insn::Nop => {}
                Insn::Ldc(c) => match pool.loadable(*c).map_err(|e| e.to_string())? {
                    BootstrapArg::Int(_) | BootstrapArg::Long(_) => {}
                    BootstrapArg::Float(_) | BootstrapArg::Double(_) => return Err(at("computes in floating point, outside this wave")),
                    _ => return Err(at("loads a constant object")),
                },
                Insn::Arith(_, Kind::Float | Kind::Double) | Insn::Convert(Kind::Float | Kind::Double, _) | Insn::Convert(_, Narrow::To(Kind::Float | Kind::Double)) => return Err(at("computes in floating point, outside this wave")),
                Insn::Cmp(c) if c.kind != Kind::Long => return Err(at("computes in floating point, outside this wave")),
                Insn::Arith(ArithOp::Div | ArithOp::Rem, _) => {
                    let constant = i > 0 && !targets.contains(offset) && nonzero_constant(class, &insns[i - 1].1);
                    if !constant {
                        return Err(at("divides by a value that may be zero, which throws: not total"));
                    }
                }
                Insn::Arith(..) | Insn::Convert(..) | Insn::Cmp(_) | Insn::If(..) | Insn::IfICmp(..) | Insn::Goto(_) => {}
                Insn::Pop | Insn::Pop2 | Insn::Dup | Insn::DupX1 | Insn::DupX2 | Insn::Dup2 | Insn::Dup2X1 | Insn::Dup2X2 | Insn::Swap => {}
                Insn::Return(Some(k)) if *k != Kind::Ref => {}
                Insn::Return(_) => return Err(at("returns no primitive")),
                Insn::TableSwitch { .. } | Insn::LookupSwitch { .. } => return Err(at("has a switch, which the lifted helper doesn't take yet")),
                Insn::InvokeStatic(m) => {
                    let callee = pool.member(*m).map_err(|e| e.to_string())?;
                    self.call(&callee).map_err(|e| at(&e))?;
                }
                Insn::InvokeVirtual(m) | Insn::InvokeSpecial(m) => {
                    let callee = pool.member(*m).map_err(|e| e.to_string())?;
                    return Err(at(&format!("calls {} on an object: only static callees are followed for now", helper_name(&callee))));
                }
                Insn::InvokeInterface(_) | Insn::InvokeDynamic(_) => return Err(at("makes a call the class path doesn't fix")),
                Insn::GetStatic(_) => return Err(at("reads a static field, outside its receiver")),
                Insn::PutStatic(_) | Insn::PutField(_) => return Err(at("writes a field: not read-only")),
                Insn::GetField(_) => return Err(at("reads a field of an object other than its receiver")),
                Insn::New(c) if pool.class_name(*c).is_ok_and(|n| self.cp.is_subtype(n, "java/lang/Throwable")) => return Err(at("creates an exception of its own: not total")),
                Insn::New(_) | Insn::NewArray(_) | Insn::ANewArray(_) | Insn::MultiANewArray(..) => return Err(at("allocates")),
                Insn::ArrayLoad(ArrayKind::Float | ArrayKind::Double) => return Err(at("computes in floating point, outside this wave")),
                Insn::ArrayLoad(ArrayKind::Ref) => return Err(at("reads an array of references")),
                Insn::ArrayLoad(_) | Insn::ArrayLength if root => {}
                Insn::ArrayLoad(_) | Insn::ArrayLength => return Err(at("reads an array, which only the helper itself may, from its receiver's fields")),
                Insn::ArrayStore(_) => return Err(at("writes an array: not read-only")),
                Insn::AThrow => return Err(at("throws an exception of its own: not total")),
                Insn::CheckCast(_) | Insn::InstanceOf(_) | Insn::IfACmp(..) | Insn::IfNull(_) | Insn::IfNonNull(_) => return Err(at("tests or casts a reference")),
                Insn::MonitorEnter | Insn::MonitorExit => return Err(at("synchronizes")),
                Insn::Jsr(_) | Insn::Ret(_) => return Err(at("has a subroutine")),
            }
            i += 1;
        }
        if let Some(m) = misuse {
            return Err(m);
        }
        if root {
            flow(class, method, &insns).map_err(|e| at(&e))?;
        }
        Ok(())
    }

    /// A `getfield` on the receiver: an instance field of a primitive, non-floating type, declared by its class or
    /// one of its superclasses.
    fn field(&mut self, field: &MemberRef) -> Result<(), String> {
        let ty = Type::parse(&field.descriptor).map_err(|e| e.to_string())?;
        let name = format!("{}.{}", field.owner.replace('/', "."), field.name);
        match &ty {
            Type::Array(inner) if matches!(**inner, Type::Float | Type::Double) => return Err(format!("reads the floating-point array field {name}, outside this wave")),
            Type::Array(inner) if !inner.is_primitive() => return Err(format!("reads the array field {name}, whose elements are references: only arrays of primitives are read")),
            _ => {}
        }
        if !ty.is_primitive() && !matches!(ty, Type::Array(_)) {
            return Err(format!("reads the reference field {name}: only primitive fields are in the footprint"));
        }
        if matches!(ty, Type::Float | Type::Double) {
            return Err(format!("reads the floating-point field {name}, outside this wave"));
        }
        if !self.cp.is_subtype(&self.receiver, &field.owner) {
            return Err(format!("reads {name}, which is not its receiver's"));
        }
        let declared_by = self.cp.resolve_field(&field.owner, &field.name, &field.descriptor).ok_or_else(|| format!("reads {name}, which the class path doesn't declare"))?;
        let Ok(Some(loaded)) = self.cp.load(&declared_by) else { return Err(format!("reads {name}, whose class can't be read")) };
        if loaded.class.fields.iter().any(|f| f.name == field.name && f.descriptor == field.descriptor && f.is_static()) {
            return Err(format!("reads {name} as an instance field, but it is static"));
        }
        if self.cp.hides_fields(&self.receiver) {
            return Err(format!("its class {} has a field hiding another, so a field's name doesn't fix it", self.receiver.replace('/', ".")));
        }
        self.fields.push(FieldRead { name: field.name.clone(), descriptor: field.descriptor.clone(), declared_by });
        Ok(())
    }

    /// A static callee: an application method whose class has no static initializer, or one of the JDK's arithmetic
    /// classes, with a primitive signature, walked under the same rules with no receiver.
    fn call(&mut self, callee: &MemberRef) -> Result<(), String> {
        let name = helper_name(callee);
        let (class, method) = self.cp.find_method(&callee.owner, &callee.name, &callee.descriptor).ok_or_else(|| format!("calls {name}, which the class path doesn't have"))?;
        let declared = MemberRef::new(&class.name, &callee.name, &callee.descriptor);
        if self.open.contains(&declared) {
            return Err(format!("is recursive, through {}", helper_name(&declared)));
        }
        if self.calls.contains(&declared) {
            return Ok(());
        }
        if !self.cp.is_application(&class.name) && !crate::equivalence::JDK_CLASSES.contains(&class.name.as_str()) {
            return Err(format!("calls {name}, outside the application and the JDK's arithmetic"));
        }
        if !method.is_static() || method.is_native() || class.is_interface() {
            return Err(format!("calls {name}, which is no static method of a class with bytecode"));
        }
        if self.cp.is_application(&class.name) {
            let mut c = Some(class.name.clone());
            while let Some(n) = c.filter(|n| self.cp.is_application(n)) {
                let Ok(Some(file)) = self.cp.application(&n) else { return Err(format!("calls {name}, whose class can't be read")) };
                if file.method("<clinit>", "()V").is_some() {
                    return Err(format!("calls {name}, whose class {} has a static initializer", n.replace('/', ".")));
                }
                c = file.super_class.clone();
            }
        }
        let descriptor = method.parsed_descriptor().map_err(|e| e.to_string())?;
        signature(&descriptor).map_err(|e| format!("calls {name}, which {}", e.trim_start_matches("it ")))?;
        self.open.push(declared.clone());
        self.method(&class, &method, false)?;
        self.open.pop();
        self.calls.push(declared);
        Ok(())
    }
}

fn where_(class: &ClassFile, method: &Method, root: bool) -> String {
    if root {
        "it".to_string()
    } else {
        format!("its callee {}", helper_name(&MemberRef::new(&class.name, &method.name, &method.descriptor)))
    }
}

/// Whether `insn` pushes a constant that is not zero.
fn nonzero_constant(class: &ClassFile, insn: &Insn) -> bool {
    match insn {
        Insn::IConst(v) => *v != 0,
        Insn::LConst(v) => *v != 0,
        Insn::Ldc(c) => matches!(class.pool.loadable(*c), Ok(BootstrapArg::Int(v)) if v != 0) || matches!(class.pool.loadable(*c), Ok(BootstrapArg::Long(v)) if v != 0),
        _ => false,
    }
}

/// What a slot of the helper's frame holds, as [`flow`] follows it.
#[derive(Debug, Clone, PartialEq, Eq)]
enum Tag {
    /// A slot of a primitive value (a `long` takes two).
    Word,
    /// Its receiver.
    Receiver,
    /// The array a field of the receiver held, by the field's name and descriptor.
    Array(String, String),
    /// A local nothing was stored in on some path, or two different values were.
    Unset,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct Frame {
    stack: Vec<Tag>,
    locals: Vec<Tag>,
}

/// The helper's code followed over every path, each slot of its stack and its locals tagged ([`Tag`]): every
/// reference it handles is its receiver, which only a `getfield` consumes, or an array one of its receiver's fields
/// held, which is only kept in a local, duplicated or popped, read by `arraylength` or loaded from by an element load
/// of its own type. A reference used any other way (passed to a call, returned, compared, written through), or two
/// different references meeting where paths join, refuses it. [`Walk::method`] has already refused every instruction
/// outside the category, so the ones left here are the ones followed.
fn flow(class: &ClassFile, method: &Method, insns: &[(u32, Insn)]) -> Result<(), String> {
    let code = method.code.as_ref().ok_or("it has no code")?;
    let descriptor = method.parsed_descriptor().map_err(|e| e.to_string())?;
    let mut locals = vec![Tag::Unset; usize::from(code.max_locals.max(1))];
    locals[0] = Tag::Receiver;
    let mut slot = 1;
    for p in &descriptor.params {
        for _ in 0..p.slots() {
            if let Some(l) = locals.get_mut(slot) {
                *l = Tag::Word;
            }
            slot += 1;
        }
    }
    let index: HashMap<u32, usize> = insns.iter().enumerate().map(|(i, (at, _))| (*at, i)).collect();
    let mut frames: Vec<Option<Frame>> = vec![None; insns.len()];
    frames[0] = Some(Frame { stack: Vec::new(), locals });
    let mut work = vec![0usize];
    let lost = || "has a stack this check can't follow".to_string();
    while let Some(i) = work.pop() {
        let mut f = frames[i].clone().expect("a frame is set before its instruction is queued");
        let insn = &insns[i].1;
        let word = |f: &mut Frame, n: usize| -> Result<(), String> {
            for _ in 0..n {
                match f.stack.pop().ok_or_else(lost)? {
                    Tag::Word => {}
                    Tag::Receiver => return Err("uses its receiver other than to read one of its fields".into()),
                    Tag::Array(name, _) => return Err(format!("uses the array of this.{name} other than to read its length or an element: it escapes, or is compared")),
                    Tag::Unset => return Err(lost()),
                }
            }
            Ok(())
        };
        let push = |f: &mut Frame, n: usize| f.stack.extend(std::iter::repeat_n(Tag::Word, n));
        let slots = |k: Kind| if k == Kind::Long { 2 } else { 1 };
        let pick = |f: &mut Frame, n: usize| -> Result<Vec<Tag>, String> {
            let at = f.stack.len().checked_sub(n).ok_or_else(lost)?;
            Ok(f.stack.split_off(at))
        };
        let mut next = true;
        match insn {
            Insn::Load(Kind::Ref, s) => {
                let t = f.locals.get(usize::from(*s)).cloned().ok_or_else(lost)?;
                if !matches!(t, Tag::Receiver | Tag::Array(..)) {
                    return Err(format!("loads local {s} as a reference where it holds no array of its receiver's on every path"));
                }
                f.stack.push(t);
            }
            Insn::Load(k, _) => push(&mut f, slots(*k)),
            Insn::Store(Kind::Ref, s) => {
                let t = f.stack.pop().ok_or_else(lost)?;
                if !matches!(t, Tag::Array(..)) {
                    return Err(format!("stores {} in local {s}", if t == Tag::Receiver { "its receiver" } else { "a value that is no array of its receiver's" }));
                }
                let s = usize::from(*s);
                *f.locals.get_mut(s).ok_or_else(lost)? = t;
            }
            Insn::Store(k, s) => {
                word(&mut f, slots(*k))?;
                let s = usize::from(*s);
                for j in s..s + slots(*k) {
                    *f.locals.get_mut(j).ok_or_else(lost)? = Tag::Word;
                }
            }
            Insn::IInc(..) | Insn::Nop => {}
            Insn::IConst(_) => push(&mut f, 1),
            Insn::LConst(_) => push(&mut f, 2),
            Insn::Ldc(c) => push(&mut f, if matches!(class.pool.loadable(*c), Ok(BootstrapArg::Long(_))) { 2 } else { 1 }),
            Insn::GetField(m) => {
                let field = class.pool.member(*m).map_err(|e| e.to_string())?;
                match f.stack.pop().ok_or_else(lost)? {
                    Tag::Receiver => {}
                    _ => return Err("reads a field of an object other than its receiver".into()),
                }
                let ty = Type::parse(&field.descriptor).map_err(|e| e.to_string())?;
                if matches!(ty, Type::Array(_)) {
                    f.stack.push(Tag::Array(field.name.clone(), field.descriptor.clone()));
                } else {
                    push(&mut f, ty.slots().into());
                }
            }
            Insn::ArrayLength => {
                if !matches!(f.stack.pop().ok_or_else(lost)?, Tag::Array(..)) {
                    return Err("takes the length of an array that is no field's of its receiver".into());
                }
                push(&mut f, 1);
            }
            Insn::ArrayLoad(kind) => {
                word(&mut f, 1)?;
                let Tag::Array(name, descriptor) = f.stack.pop().ok_or_else(lost)? else { return Err("loads an element of an array that is no field's of its receiver".into()) };
                let fits = matches!(
                    (kind, &descriptor[1..]),
                    (ArrayKind::Int, "I") | (ArrayKind::Long, "J") | (ArrayKind::Byte, "B" | "Z") | (ArrayKind::Char, "C") | (ArrayKind::Short, "S")
                );
                if !fits {
                    return Err(format!("loads an element of this.{name} ({descriptor}) by an instruction of another type"));
                }
                push(&mut f, if *kind == ArrayKind::Long { 2 } else { 1 });
            }
            Insn::Arith(op, k) => {
                let n = slots(*k);
                match op {
                    ArithOp::Neg => word(&mut f, n)?,
                    ArithOp::Shl | ArithOp::Shr | ArithOp::Ushr => word(&mut f, 1 + n)?,
                    _ => word(&mut f, 2 * n)?,
                }
                push(&mut f, n);
            }
            Insn::Convert(from, to) => {
                word(&mut f, slots(*from))?;
                push(&mut f, if *to == Narrow::To(Kind::Long) { 2 } else { 1 });
            }
            Insn::Cmp(_) => {
                word(&mut f, 4)?;
                push(&mut f, 1);
            }
            Insn::If(..) => word(&mut f, 1)?,
            Insn::IfICmp(..) => word(&mut f, 2)?,
            Insn::Goto(_) => next = false,
            Insn::Return(Some(k)) => {
                word(&mut f, slots(*k))?;
                next = false;
            }
            Insn::InvokeStatic(m) => {
                let callee = class.pool.member(*m).map_err(|e| e.to_string())?;
                let d = MethodDescriptor::parse(&callee.descriptor).map_err(|e| e.to_string())?;
                word(&mut f, d.params.iter().map(|p| usize::from(p.slots())).sum())?;
                push(&mut f, d.ret.slots().into());
            }
            Insn::Pop => drop(pick(&mut f, 1)?),
            Insn::Pop2 => drop(pick(&mut f, 2)?),
            Insn::Dup => {
                let v = pick(&mut f, 1)?;
                f.stack.extend(v.clone().into_iter().chain(v));
            }
            Insn::Dup2 => {
                let v = pick(&mut f, 2)?;
                f.stack.extend(v.clone().into_iter().chain(v));
            }
            Insn::DupX1 | Insn::DupX2 | Insn::Dup2X1 | Insn::Dup2X2 => {
                let (top, under) = match insn {
                    Insn::DupX1 => (1, 1),
                    Insn::DupX2 => (1, 2),
                    Insn::Dup2X1 => (2, 1),
                    _ => (2, 2),
                };
                let v = pick(&mut f, top)?;
                let u = pick(&mut f, under)?;
                f.stack.extend(v.clone().into_iter().chain(u).chain(v));
            }
            Insn::Swap => {
                let v = pick(&mut f, 2)?;
                f.stack.extend([v[1].clone(), v[0].clone()]);
            }
            other => return Err(format!("has the instruction {other:?}, which this check doesn't follow")),
        }
        let mut successors: Vec<usize> = insn.targets().iter().map(|t| index.get(t).copied().ok_or_else(lost)).collect::<Result<_, _>>()?;
        if next {
            successors.push(i + 1);
        }
        for j in successors {
            if j >= insns.len() {
                return Err(lost());
            }
            let merged = match &frames[j] {
                None => f.clone(),
                Some(old) => {
                    if old.stack.len() != f.stack.len() {
                        return Err(lost());
                    }
                    let mut m = old.clone();
                    for (a, b) in m.stack.iter_mut().zip(&f.stack) {
                        if a != b {
                            return Err("meets two different references, or a reference and a value, where its paths join".into());
                        }
                    }
                    for (a, b) in m.locals.iter_mut().zip(&f.locals) {
                        if a != b {
                            *a = Tag::Unset;
                        }
                    }
                    m
                }
            };
            if frames[j].as_ref() != Some(&merged) {
                frames[j] = Some(merged);
                work.push(j);
            }
        }
    }
    Ok(())
}

/// A helper lifted over its footprint: [`lift`]'s result.
#[derive(Debug, Clone)]
pub struct Lifted {
    /// The lifted static method: `quotes/QuoteService$Footprint$fee`, `fee`, `(IJ)J`.
    pub method: MemberRef,
    /// Its class file, of its own.
    pub bytes: Vec<u8>,
}

impl Lifted {
    /// `quotes.QuoteService$Footprint$fee#fee`: the lifted method as the regression check's target names it.
    pub fn target(&self) -> String {
        format!("{}#{}", self.method.owner.replace('/', "."), self.method.name)
    }
}

/// The helper of `footprint` (on `cp`, the version it was established on) as a static method over its arguments and
/// then the values of `fields`, which hold every field it reads and may hold more (another version's), in the order
/// given (see the module's documentation).
pub fn lift(cp: &ClassPath, footprint: &Footprint, fields: &[FieldRead]) -> Result<Lifted, Unsupported> {
    let helper = &footprint.helper;
    let refuse = |why: String| refused(helper, why);
    if let Some(missing) = footprint.fields.iter().find(|f| !fields.contains(f)) {
        return Err(refuse(format!("it reads {}, which its lifting leaves out", missing.name)));
    }
    let (class, method) = cp.find_method(&helper.owner, &helper.name, &helper.descriptor).ok_or_else(|| refuse("the class path has no such method".into()))?;
    let package = helper.owner.rsplit_once('/').map(|(p, _)| p);
    for callee in &footprint.calls {
        let Some((c, m)) = cp.find_method(&callee.owner, &callee.name, &callee.descriptor) else { continue };
        let same_package = c.name.rsplit_once('/').map(|(p, _)| p) == package;
        let reachable = (m.is_public() && (c.access & flags::PUBLIC != 0)) || (same_package && !m.is_private());
        // Only the helper's own calls are made from the lifted class; its callees' calls stay in their classes.
        let direct = callee_of(&class, &method, callee);
        if direct && !reachable {
            return Err(refuse(format!("it calls {}, which a lifted copy in a class of its own can't reach", helper_name(callee))));
        }
    }
    let lifted_class = format!("{}{LIFTED}{}", helper.owner, helper.name);
    if cp.exists(&lifted_class) {
        return Err(refuse(format!("its lifted class {} is already on the class path", lifted_class.replace('/', "."))));
    }
    let code = method.code.as_ref().ok_or_else(|| refuse("it has no code".into()))?;
    let insns = code.instructions().map_err(|e| refuse(e.to_string()))?;
    let params: u16 = footprint.params.iter().map(Type::slots).sum();
    let mut slot_of = HashMap::new();
    let mut next = params;
    for f in fields {
        slot_of.insert((f.name.clone(), f.descriptor.clone()), next);
        next += f.ty().slots();
    }
    let widths = next - params;
    // Local 0 (the receiver) goes; its parameters move down one, its other locals past the fields' values.
    let local = |old: u16| if old <= params { old - 1 } else { old - 1 + widths };
    let mut w = ClassWriter::new(&lifted_class);
    let mut b = CodeBuilder::new();
    let mut labels = HashMap::new();
    for t in insns.iter().flat_map(|(_, i)| i.targets()) {
        labels.entry(t).or_insert_with(|| b.label());
    }
    let label = |labels: &HashMap<u32, crate::classfile::writer::Label>, t: &u32| labels[t];
    let mut i = 0;
    while i < insns.len() {
        let (offset, insn) = &insns[i];
        if let Some(l) = labels.get(offset) {
            b.bind(*l);
        }
        match insn {
            Insn::Load(Kind::Ref, 0) => {
                let Some((_, Insn::GetField(f))) = insns.get(i + 1) else { return Err(refuse("its receiver is used other than by a field read".into())) };
                let field = class.pool.member(*f).map_err(|e| refuse(e.to_string()))?;
                let slot = slot_of[&(field.name.clone(), field.descriptor.clone())];
                b.load(kind_of(&Type::parse(&field.descriptor).map_err(|e| refuse(e.to_string()))?), slot);
                i += 2;
                continue;
            }
            Insn::Load(k, s) => b.load(*k, local(*s)),
            Insn::Store(k, s) => b.store(*k, local(*s)),
            Insn::IInc(s, d) => {
                let d = i8::try_from(*d).map_err(|_| refuse("it has a wide increment, which the lifted helper doesn't take yet".into()))?;
                b.iinc(local(*s), d);
            }
            Insn::IConst(v) => b.iconst(*v),
            Insn::LConst(v) => b.op(0x09 + *v as u8),
            Insn::Ldc(c) => match class.pool.loadable(*c).map_err(|e| refuse(e.to_string()))? {
                BootstrapArg::Int(v) => {
                    let index = w.pool.integer(v);
                    b.ldc(index);
                }
                BootstrapArg::Long(v) => {
                    let index = w.pool.long(v);
                    b.ldc2(index);
                }
                _ => return Err(refuse("it loads a constant object".into())),
            },
            Insn::Nop => b.op(0x00),
            Insn::Pop => b.op(0x57),
            Insn::Pop2 => b.op(0x58),
            Insn::Dup => b.op(0x59),
            Insn::DupX1 => b.op(0x5a),
            Insn::DupX2 => b.op(0x5b),
            Insn::Dup2 => b.op(0x5c),
            Insn::Dup2X1 => b.op(0x5d),
            Insn::Dup2X2 => b.op(0x5e),
            Insn::Swap => b.op(0x5f),
            Insn::Arith(op, k) => b.op(arith_opcode(*op, *k).ok_or_else(|| refuse("it computes in floating point".into()))?),
            Insn::Convert(from, to) => b.op(convert_opcode(*from, *to).ok_or_else(|| refuse("it computes in floating point".into()))?),
            Insn::Cmp(c) if c.kind == Kind::Long => b.op(0x94),
            Insn::If(c, t) => b.if_zero(*c, label(&labels, t)),
            Insn::IfICmp(c, t) => b.if_icmp(*c, label(&labels, t)),
            Insn::Goto(t) => b.goto(label(&labels, t)),
            Insn::Return(k) => b.return_(*k),
            Insn::InvokeStatic(m) => {
                let callee = class.pool.member(*m).map_err(|e| refuse(e.to_string()))?;
                let index = w.pool.method_ref(&callee.owner, &callee.name, &callee.descriptor);
                b.op_u16(0xb8, index);
            }
            Insn::ArrayLength => b.op(0xbe),
            Insn::ArrayLoad(k) => b.op(match k {
                ArrayKind::Int => 0x2e,
                ArrayKind::Long => 0x2f,
                ArrayKind::Byte => 0x33,
                ArrayKind::Char => 0x34,
                ArrayKind::Short => 0x35,
                _ => return Err(refuse(format!("its array load {k:?} has no lifted form"))),
            }),
            other => return Err(refuse(format!("its instruction {other:?} has no lifted form"))),
        }
        i += 1;
    }
    b.max_stack = code.max_stack;
    b.max_locals = b.max_locals.max(code.max_locals.saturating_sub(1) + widths).max(params + widths);
    let lifted_descriptor = MethodDescriptor::new(footprint.params.iter().cloned().chain(fields.iter().map(FieldRead::ty)).collect(), footprint.result.clone()).descriptor();
    w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: helper.name.clone(), descriptor: lifted_descriptor.clone(), code: Some(b) });
    Ok(Lifted { method: MemberRef::new(&lifted_class, &helper.name, &lifted_descriptor), bytes: w.to_bytes() })
}

/// The suffix of the classes holding a summary's call-site adapters: `quotes/QuoteService$Footprint$fee$Call`, and
/// `before/quotes/QuoteService$Footprint$fee$Call` for the previous version.
pub const CALL: &str = "$Call";

/// A summary's adapters at the call site ([`adapters`]): one static method per version, each in a class of its own in
/// its version's package, which takes what a call of the helper leaves on the stack (the receiver, then the
/// arguments), reads the footprint's fields from that receiver as its own version lays them out, and calls the one
/// lifted helper both versions share.
#[derive(Debug, Clone)]
pub struct Adapters {
    /// The previous version's adapter: `before/quotes/QuoteService$Footprint$fee$Call`, `before`,
    /// `(Lbefore/quotes/QuoteService;I)J`.
    pub before: MemberRef,
    /// The new version's: `quotes/QuoteService$Footprint$fee$Call`, `after`, `(Lquotes/QuoteService;I)J`.
    pub after: MemberRef,
    /// Their class files: the previous version's, and the new one's.
    pub before_bytes: Vec<u8>,
    pub after_bytes: Vec<u8>,
}

/// The adapters of the helper `helper` (as the new version declares it, with `params` and `result`; `private` in the
/// previous version and the new one, or not)
/// lifted over `fields` into `lifted`, the new version's lifted helper; the previous version's classes are relocated
/// under `prefix` (`before`), its receiver class and the classes declaring its fields included. Each adapter loads the
/// arguments, then each field of `fields` from the actual receiver (its first read throws the `NullPointerException`
/// a call on `null` throws, before anything else runs, as the call would), and returns the lifted helper's outcome.
/// So a call through an adapter reads the receiver's state at that call, never an earlier one. `fields` must not be
/// empty: with nothing read, the receiver's null check would be left out.
///
/// **An array field** is in the summary's domain only when it holds an array, of at most `bound` elements: the lifted
/// proof's harness makes no `null` array and none longer. So each adapter first checks every array field of the
/// actual receiver, and where one is `null` or longer it calls its own version's helper on the receiver, its body as
/// written, instead of the lifted helper: the summary is applied only at a call whose state its domain covers, and
/// elsewhere the body stays. (The adapters are the checker's classes, never run on a JVM for a witness: a private
/// helper is called by `invokespecial` from the adapter's class as the checker resolves it.)
pub fn adapters(helper: &MemberRef, params: &[Type], result: &Type, fields: &[FieldRead], lifted: &MemberRef, prefix: &str, bound: u32, private: (bool, bool)) -> Result<Adapters, Unsupported> {
    if fields.is_empty() {
        return Err(refused(helper, "it reads no field of its receiver, so an adapter would leave out the null check of its call"));
    }
    let ret = kind_of(result);
    // In its version's package, so that it reads a package-private field, and calls a package-private helper outside
    // the domain, as a class of that package may.
    let method = |name: &str, owner: &dyn Fn(&str) -> String, private: bool| -> (MemberRef, Vec<u8>) {
        let class = owner(&format!("{}{LIFTED}{}{CALL}", helper.owner, helper.name));
        let mut w = ClassWriter::new(&class);
        let descriptor = MethodDescriptor::new(std::iter::once(Type::Object(owner(&helper.owner))).chain(params.iter().cloned()).collect(), result.clone()).descriptor();
        let mut b = CodeBuilder::new();
        let body = b.label();
        let arrays: Vec<&FieldRead> = fields.iter().filter(|f| f.is_array()).collect();
        for f in &arrays {
            let index = w.pool.field_ref(&owner(&f.declared_by), &f.name, &f.descriptor);
            b.load(Kind::Ref, 0);
            b.op_u16(0xb4, index); // getfield
            b.if_null(body);
            b.load(Kind::Ref, 0);
            b.op_u16(0xb4, index);
            b.op(0xbe); // arraylength
            let limit = w.pool.integer(i32::try_from(bound).unwrap_or(i32::MAX));
            b.ldc(limit);
            b.if_icmp(crate::classfile::Cond::Gt, body);
        }
        let mut slot = 1u16;
        for p in params {
            b.load(kind_of(p), slot);
            slot += p.slots();
        }
        let mut stack = slot - 1;
        for f in fields {
            b.load(Kind::Ref, 0);
            let index = w.pool.field_ref(&owner(&f.declared_by), &f.name, &f.descriptor);
            b.op_u16(0xb4, index); // getfield
            stack += f.ty().slots();
        }
        let index = w.pool.method_ref(&lifted.owner, &lifted.name, &lifted.descriptor);
        b.op_u16(0xb8, index); // invokestatic
        b.return_(Some(ret));
        if !arrays.is_empty() {
            // Outside the domain: the version's own helper, on the receiver, as the call was.
            b.bind(body);
            b.load(Kind::Ref, 0);
            let mut s = 1u16;
            for p in params {
                b.load(kind_of(p), s);
                s += p.slots();
            }
            let index = w.pool.method_ref(&owner(&helper.owner), &helper.name, &helper.descriptor);
            b.op_u16(if private { 0xb7 } else { 0xb6 }, index); // invokespecial, invokevirtual
            b.return_(Some(ret));
        }
        b.max_stack = (stack + 1).max(result.slots()).max(2).max(slot);
        b.max_locals = slot;
        w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: name.to_string(), descriptor: descriptor.clone(), code: Some(b) });
        (MemberRef::new(&class, name, &descriptor), w.to_bytes())
    };
    let (before, before_bytes) = method("before", &|c: &str| format!("{prefix}/{c}"), private.0);
    let (after, after_bytes) = method("after", &|c: &str| c.to_string(), private.1);
    Ok(Adapters { before, after, before_bytes, after_bytes })
}

/// Whether `method`'s own code calls `callee` (a static method, as declared or as named).
fn callee_of(class: &ClassFile, method: &Method, callee: &MemberRef) -> bool {
    let Some(code) = &method.code else { return false };
    let Ok(insns) = code.instructions() else { return false };
    insns.iter().any(|(_, i)| matches!(i, Insn::InvokeStatic(m) if class.pool.member(*m).is_ok_and(|r| r.name == callee.name && r.descriptor == callee.descriptor)))
}

fn kind_of(t: &Type) -> Kind {
    match t {
        Type::Long => Kind::Long,
        Type::Float => Kind::Float,
        Type::Double => Kind::Double,
        Type::Object(_) | Type::Array(_) => Kind::Ref,
        _ => Kind::Int,
    }
}

fn arith_opcode(op: ArithOp, k: Kind) -> Option<u8> {
    let wide = match k {
        Kind::Int => 0,
        Kind::Long => 1,
        _ => return None,
    };
    Some(match op {
        ArithOp::Add => 0x60 + wide,
        ArithOp::Sub => 0x64 + wide,
        ArithOp::Mul => 0x68 + wide,
        ArithOp::Div => 0x6c + wide,
        ArithOp::Rem => 0x70 + wide,
        ArithOp::Neg => 0x74 + wide,
        ArithOp::Shl => 0x78 + wide,
        ArithOp::Shr => 0x7a + wide,
        ArithOp::Ushr => 0x7c + wide,
        ArithOp::And => 0x7e + wide,
        ArithOp::Or => 0x80 + wide,
        ArithOp::Xor => 0x82 + wide,
    })
}

fn convert_opcode(from: Kind, to: Narrow) -> Option<u8> {
    Some(match (from, to) {
        (Kind::Int, Narrow::To(Kind::Long)) => 0x85,
        (Kind::Long, Narrow::To(Kind::Int)) => 0x88,
        (Kind::Int, Narrow::Byte) => 0x91,
        (Kind::Int, Narrow::Char) => 0x92,
        (Kind::Int, Narrow::Short) => 0x93,
        _ => return None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_opcodes_written_are_the_ones_read() {
        for (op, k) in [(ArithOp::Add, Kind::Int), (ArithOp::Rem, Kind::Long), (ArithOp::Ushr, Kind::Long), (ArithOp::Xor, Kind::Int), (ArithOp::Neg, Kind::Long)] {
            let byte = arith_opcode(op, k).unwrap();
            assert_eq!(crate::classfile::bytecode::decode(&[byte]).unwrap(), [(0, Insn::Arith(op, k))]);
        }
        for (from, to) in [(Kind::Int, Narrow::To(Kind::Long)), (Kind::Long, Narrow::To(Kind::Int)), (Kind::Int, Narrow::Char)] {
            assert_eq!(crate::classfile::bytecode::decode(&[convert_opcode(from, to).unwrap()]).unwrap(), [(0, Insn::Convert(from, to))]);
        }
    }
}
