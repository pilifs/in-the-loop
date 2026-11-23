//! For a newly constructed key, no earlier thread-local map entry can refer to it. On the sole
//! executing platform thread, the key retains exactly its most recently bound reference, including null.
//! Inherited bindings from a parent thread and maps or keys from observed startup stay outside this rule.
use super::*;
use crate::classfile::MemberRef;

const LOCAL: &str = "java/lang/ThreadLocal";
const INHERITABLE: &str = "java/lang/InheritableThreadLocal";
pub(super) const FRESH: &str = "<JVM.ThreadLocal.fresh>";
pub(super) const BINDING: &str = "<JVM.ThreadLocal.binding>";

impl Engine<'_> {
    pub(super) fn fresh_thread_local(&mut self, path: &mut Path, o: usize, special: bool, m: &MemberRef, args: &[Val]) -> Option<Step> {
        let constructor = special && m.name == "<init>" && m.descriptor == "()V"
            && matches!(m.owner.as_str(), LOCAL | INHERITABLE);
        if !constructor && !path.objects[o].fields.contains_key(FRESH) { return None; }
        if constructor {
            if path.objects[o].assumed || path.objects[o].given || path.objects[o].unknown { return None; }
            let mut class = path.objects[o].class.clone();
            while self.cp.is_application(&class) { class = self.cp.superclass(&class)?; }
            if !matches!(class.as_str(), LOCAL | INHERITABLE) || !self.cp.thread_local_keys() { return None; }
            if m.owner == INHERITABLE {
                let (cf, method) = self.cp.find_method(INHERITABLE, "<init>", "()V")?;
                return Some(self.enter_method(path, INHERITABLE, cf, method, vec![Val::R(Some(o))]));
            }
            if let Err(stop) = self.keeps(path, None, "allocates a ThreadLocal key from the JVM's shared hash counter") { return Some(Err(stop)); }
            path.objects[o].fields.insert(FRESH.into(), Val::I(self.b.constant(1, 32)));
        } else {
            let lookup = if special { &m.owner } else { &path.objects[o].class };
            if !matches!((m.name.as_str(), m.descriptor.as_str()),
                ("get", "()Ljava/lang/Object;") | ("set", "(Ljava/lang/Object;)V") | ("remove", "()V"))
                || self.cp.find_method(lookup, &m.name, &m.descriptor)?.0.name != LOCAL { return None; }
            self.assumed.insert("fresh ThreadLocal keys are used on the one executing platform thread of the check".into());
            // Even get may install the first binding. A summarized pure caller cannot hide a write to the thread.
            if let Err(stop) = self.keeps(path, None, "uses the current thread's ThreadLocal map") { return Some(Err(stop)); }
            match (m.name.as_str(), args) {
                ("set", [v]) => { path.objects[o].fields.insert(BINDING.into(), v.clone()); }
                ("remove", []) => { path.objects[o].fields.remove(BINDING); }
                ("get", []) => {
                    if !path.objects[o].fields.contains_key(BINDING) {
                        let (class, method) = self.cp.find_method(&path.objects[o].class, "initialValue", "()Ljava/lang/Object;")?;
                        if class.name != LOCAL {
                            if !self.cp.is_application(&class.name) || method.code.is_none() {
                                return Some(unsupported("ThreadLocal.get with an unqualified initialValue implementation"));
                            }
                            let old_depth = path.frames.len();
                            return Some(self.enter_method(path, LOCAL, class, method, vec![Val::R(Some(o))]).and_then(|step| {
                                if step.is_some() || path.frames.len() != old_depth + 1 {
                                    return unsupported("ThreadLocal.initialValue did not enter its application frame");
                                }
                                path.frames.last_mut().expect("initialValue frame").thread_local_key = Some(o);
                                Ok(None)
                            }));
                        }
                        path.objects[o].fields.insert(BINDING.into(), Val::R(None));
                    }
                    self.push(path, path.objects[o].fields[BINDING].clone());
                }
                _ => return None,
            }
        }
        self.advance(path);
        Some(Ok(None))
    }
}
