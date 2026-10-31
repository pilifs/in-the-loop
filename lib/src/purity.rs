//! Proves, from bytecode, that a method is a pure function of its arguments: running it twice on equal arguments
//! gives equal results, and it changes nothing outside the objects it creates. Without that, executing every input
//! would prove nothing.
//!
//! The analysis walks every application method the target can reach, following virtual calls through sealed
//! hierarchies (a closed world) and rejecting calls whose implementations it cannot enumerate. In those methods it
//! rejects: writes to static fields; reads of mutable static fields; writes to fields outside constructors; native
//! methods; and calls into the JDK that are not on the short list of APIs in [`crate::trusted`]. That list is the
//! trusted base.
//!
//! This static proof is complemented by the interpreter's dynamic effect monitor ([`crate::interp`]), which
//! rejects a write to any object that existed before the call, including stores into arrays and collections that
//! the static analysis does not track. Because every input of the domain is executed, the dynamic check is
//! complete over the domain, and the two together close the gap the static analysis leaves.

use std::collections::{BTreeSet, HashSet, VecDeque};

use serde::Serialize;

use crate::classfile::{flags, BootstrapArg, ClassFile, Insn, MemberRef, Method};
use crate::classpath::ClassPath;

/// The outcome of the purity analysis of one method.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct PurityResult {
    /// Every application method reached, as `pkg.Class.method`.
    pub reached: BTreeSet<String>,
    /// Every JDK entry relied on, as `pkg.Class.method`.
    pub trusted: BTreeSet<String>,
    pub violations: Vec<String>,
    /// The first source line of the target, for reports (0 when unknown).
    pub first_line: u32,
}

impl PurityResult {
    pub fn is_pure(&self) -> bool {
        self.violations.is_empty()
    }
}

pub struct Purity<'a> {
    cp: &'a ClassPath,
}

struct State {
    reached: Vec<MemberRef>,
    seen: HashSet<MemberRef>,
    work: VecDeque<MemberRef>,
    trusted: BTreeSet<String>,
    violations: Vec<String>,
}

impl<'a> Purity<'a> {
    pub fn new(cp: &'a ClassPath) -> Purity<'a> {
        Purity { cp }
    }

    /// Analyses `owner.name(descriptor)` and everything it reaches.
    pub fn analyse(&self, owner: &str, name: &str, descriptor: &str) -> PurityResult {
        let root = MemberRef::new(owner, name, descriptor);
        let mut state = State { reached: Vec::new(), seen: HashSet::new(), work: VecDeque::new(), trusted: BTreeSet::new(), violations: Vec::new() };
        state.work.push_back(root.clone());
        let mut first_line = 0;
        while let Some(reference) = state.work.pop_front() {
            if !state.seen.insert(reference.clone()) {
                continue;
            }
            state.reached.push(reference.clone());
            let Some((class, method)) = self.declared(&reference) else {
                state.violations.push(format!("{reference}: no bytecode found"));
                continue;
            };
            if method.is_native() {
                state.violations.push(format!("{reference} is native"));
                continue;
            }
            let Some(code) = &method.code else {
                continue; // abstract: its implementations were enqueued by the dispatch
            };
            if reference == root {
                first_line = code.first_line().map(u32::from).unwrap_or(0);
            }
            let constructor = reference.name == "<init>";
            let insns = match code.instructions() {
                Ok(i) => i,
                Err(e) => {
                    state.violations.push(format!("{reference}: {e}"));
                    continue;
                }
            };
            for (_, insn) in insns {
                match insn {
                    Insn::GetStatic(i) | Insn::PutStatic(i) | Insn::GetField(i) | Insn::PutField(i) => {
                        if let Ok(field) = class.pool.member(i) {
                            self.check_field(&reference, &insn, &field, constructor, &mut state);
                        }
                    }
                    Insn::InvokeVirtual(i) | Insn::InvokeInterface(i) => {
                        if let Ok(target) = class.pool.member(i) {
                            self.dispatch(&reference, &target, true, &mut state);
                        }
                    }
                    Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) => {
                        if let Ok(target) = class.pool.member(i) {
                            self.dispatch(&reference, &target, false, &mut state);
                        }
                    }
                    Insn::InvokeDynamic(i) => self.check_indy(&reference, &class, i, &mut state),
                    _ => {}
                }
            }
        }
        PurityResult {
            reached: state.reached.iter().map(MemberRef::display).collect(),
            trusted: state.trusted,
            violations: state.violations,
            first_line,
        }
    }

    fn check_field(&self, in_: &MemberRef, insn: &Insn, field: &MemberRef, constructor: bool, state: &mut State) {
        let where_ = format!("{}.{}", field.owner.replace('/', "."), field.name);
        match insn {
            Insn::PutStatic(_) => state.violations.push(format!("{in_} writes static field {where_}")),
            Insn::PutField(_) => {
                if !constructor {
                    state.violations.push(format!("{in_} writes field {where_} outside a constructor"));
                }
            }
            Insn::GetStatic(_) => {
                if !self.cp.is_application(&field.owner) {
                    state.violations.push(format!("{in_} reads JDK static field {where_}"));
                } else if self.cp.is_final_field(&field.owner, &field.name) != Some(true) {
                    state.violations.push(format!("{in_} reads mutable static field {where_}"));
                }
            }
            _ => {}
        }
    }

    fn check_indy(&self, in_: &MemberRef, class: &ClassFile, index: u16, state: &mut State) {
        let Ok((bootstrap_index, _, _)) = class.pool.invoke_dynamic(index) else {
            state.violations.push(format!("{in_} uses a malformed invokedynamic"));
            return;
        };
        let bootstraps = class.bootstrap_methods().unwrap_or_default();
        let Some(bootstrap) = bootstraps.get(bootstrap_index as usize) else {
            state.violations.push(format!("{in_} uses invokedynamic with a missing bootstrap method"));
            return;
        };
        let owner = &bootstrap.method.member.owner;
        if crate::trusted::is_pure_bootstrap(owner) {
            state.trusted.insert(format!("{}.{}", owner.replace('/', "."), bootstrap.method.member.name));
        } else if owner == "java/lang/invoke/LambdaMetafactory" {
            match bootstrap.args.get(1) {
                // A lambda body, or a method reference: an application method to walk, or a JDK one to trust.
                Some(BootstrapArg::MethodHandle(handle)) if self.cp.is_application(&handle.member.owner) => {
                    state.work.push_back(handle.member.clone());
                }
                Some(BootstrapArg::MethodHandle(handle)) => self.check_jdk(in_, &handle.member, state),
                _ => state.violations.push(format!("{in_} creates a lambda with an unknown implementation")),
            }
        } else {
            state.violations.push(format!("{in_} uses invokedynamic with bootstrap L{owner};"));
        }
    }

    /// Enqueues every implementation a call can reach, or records why it cannot be enumerated.
    fn dispatch(&self, in_: &MemberRef, call: &MemberRef, virtual_: bool, state: &mut State) {
        if call.owner.starts_with('[') {
            state.trusted.insert(format!("array.{}", call.name)); // clone() of an array
            return;
        }
        if !self.cp.exists(&call.owner) {
            state.violations.push(format!("{in_} calls {call}, whose class cannot be loaded"));
            return;
        }
        if !self.cp.is_application(&call.owner) {
            self.check_jdk(in_, call, state);
            return;
        }
        // The implementation that runs for an instance of the owner itself. It may be inherited from a superclass,
        // possibly a JDK one, such as Enum.ordinal().
        let resolved = self.resolve(call);
        match &resolved {
            None => {
                if !virtual_ {
                    state.violations.push(format!("{in_} calls {call}, which cannot be resolved"));
                    return;
                }
            }
            Some(r) if self.cp.is_application(&r.owner) => state.work.push_back(r.clone()),
            Some(r) => self.check_jdk(in_, r, state),
        }
        // Overrides in subclasses, for a virtual call.
        if !virtual_ || self.cp.is_effectively_final(&call.owner) || self.is_private_or_final(resolved.as_ref()) {
            return;
        }
        let Ok(Some(owner)) = self.cp.application(&call.owner) else { return };
        if !owner.is_sealed() {
            state.violations.push(format!(
                "{in_} calls {call} virtually on {}, which is open to implementations outside the analysed code",
                call.owner.replace('/', ".")
            ));
            return;
        }
        for sub in owner.permitted_subclasses().unwrap_or_default() {
            let target = MemberRef { owner: sub, name: call.name.clone(), descriptor: call.descriptor.clone(), interface: false };
            self.dispatch(in_, &target, true, state);
        }
    }

    fn check_jdk(&self, in_: &MemberRef, call: &MemberRef, state: &mut State) {
        if crate::trusted::is_pure(&call.owner, &call.name) {
            state.trusted.insert(call.display());
        } else {
            state.violations.push(format!("{in_} calls {call}, which is not known to be pure"));
        }
    }

    /// The class that declares the method an instance of `call.owner` runs, or `None` if it is abstract.
    fn resolve(&self, call: &MemberRef) -> Option<MemberRef> {
        let mut owner = Some(call.owner.clone());
        while let Some(current) = owner {
            let Ok(Some(class)) = self.cp.application(&current) else {
                // Into the JDK: match by name, which is enough to decide trust.
                return self.cp.jdk_declaring_class(&current, &call.name).map(|c| MemberRef { owner: c, name: call.name.clone(), descriptor: call.descriptor.clone(), interface: false });
            };
            if let Some(m) = class.method(&call.name, &call.descriptor) {
                return if m.code.is_some() || m.is_native() {
                    Some(MemberRef { owner: current, name: call.name.clone(), descriptor: call.descriptor.clone(), interface: false })
                } else {
                    None
                };
            }
            owner = class.super_class.clone();
        }
        None
    }

    fn declared(&self, reference: &MemberRef) -> Option<(std::rc::Rc<ClassFile>, Method)> {
        let class = self.cp.application(&reference.owner).ok().flatten()?;
        let method = class.method(&reference.name, &reference.descriptor)?.clone();
        Some((class, method))
    }

    fn is_private_or_final(&self, reference: Option<&MemberRef>) -> bool {
        reference
            .and_then(|r| self.declared(r))
            .map(|(_, m)| m.access & (flags::PRIVATE | flags::FINAL) != 0)
            .unwrap_or(false)
    }
}
