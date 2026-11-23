//! A fresh JDK reference queue may deliver a registered soft reference once, in
//! any order, or return null. Collection and delivery need not happen together.
//! Overapproximate GC eligibility, retaining object identity and one-way clearing.
use super::*;

const SOFT: &str = "java/lang/ref/SoftReference";
const REFERENCE: &str = "java/lang/ref/Reference";
const CLEARED: &str = "<GC.cleared>";
const POLLED: &str = "<GC.polled>";
const COLLECTION: &str = "the JVM's soft-reference clearing and queue delivery";
pub(super) const FRESH_QUEUE: &str = "<JDK.freshReferenceQueue>";

impl Engine<'_> {
    pub(super) fn register_reference(&self, path: &mut Path, o: usize, queue: &Val) {
        let fields = &mut path.objects[o].fields;
        fields.insert(runtime::REGISTERED_QUEUE.into(), queue.clone());
        fields.insert(CLEARED.into(), Val::I(self.b.constant(0, 32)));
        fields.insert(POLLED.into(), Val::I(self.b.constant(0, 32)));
    }

    fn gc_flag(&self, path: &Path, o: usize, flag: &str) -> Result<Lit, Stop> {
        match path.objects[o].fields.get(flag) {
            Some(Val::I(word)) => Ok(word[0]),
            _ => unsupported("an unknown soft-reference state"),
        }
    }

    pub(super) fn poll_reference_queue(&mut self, path: &mut Path, queue: usize) -> Step {
        let mut candidates = Vec::new();
        for (id, obj) in path.objects.iter().enumerate() {
            if let Some(original) = obj.fields.get(runtime::REGISTERED_QUEUE) {
                let targets = original.options().ok_or_else(|| Stop::Unsupported("unknown registration queue".into()))?;
                if let Some((guard, _)) = targets.into_iter().find(|(_, target)| *target == Some(queue)) {
                    candidates.push((id, guard));
                }
            } else if id > queue && self.cp.is_subtype(&obj.class, REFERENCE) {
                return unsupported(format!("polling a queue with an untracked {} registration", obj.class.replace('/', ".")));
            }
        }
        if !candidates.is_empty() && (self.gap_mode != GapMode::Strict || !self.cp.soft_queue_image()) {
            return unsupported("polling a reference queue after a possible GC registration on an unqualified image");
        }
        if self.there_before(path, queue) { self.reads(path, || "reads a reference queue".into())?; }
        let mut available = TRUE;
        let mut options = Vec::new();
        for (id, registered) in candidates {
            if !self.cp.is_subtype(&path.objects[id].class, SOFT) { return unsupported("a registered reference outside the soft-reference model"); }
            self.keeps(path, Some(queue), "removes a possibly enqueued reference")?;
            self.keeps(path, Some(id), "records delivery of a soft reference")?;
            let polled = self.gc_flag(path, id, POLLED)?;
            let cleared = self.gc_flag(path, id, CLEARED)?;
            let unconsumed = self.b.and(registered, -polled);
            let eligible = self.b.and(available, unconsumed);
            let gc = self.b.var();
            let delivered = self.b.and(eligible, gc);
            available = self.b.and(available, -delivered);
            options.push((delivered, Some(id)));
            let was_polled = self.b.or(polled, delivered);
            let was_cleared = self.b.or(cleared, delivered);
            let fields = &mut path.objects[id].fields;
            fields.insert(POLLED.into(), Val::I(self.b.zext(&vec![was_polled], 32)));
            fields.insert(CLEARED.into(), Val::I(self.b.zext(&vec![was_cleared], 32)));
            path.unbound_platform_value = Some(COLLECTION);
        }
        options.push((available, None));
        let value = choice(&mut self.b, options);
        self.push(path, value);
        self.advance(path);
        Ok(None)
    }

    /// The pinned SoftReference.get runs its real timestamp logic. Its call to
    /// Reference.get returns the original referent or a permanently cleared null.
    pub(super) fn soft_reference_get(&mut self, path: &mut Path, id: usize, owner: &str, special: bool) -> Option<Step> {
        if self.gap_mode != GapMode::Strict || !self.cp.soft_queue_image() { return None; }
        if special && owner == REFERENCE {
            return Some(self.soft_referent(path, id));
        }
        let receiver = if special { owner } else { &path.objects[id].class };
        let (class, method) = self.cp.find_method(receiver, "get", "()Ljava/lang/Object;")?;
        if class.name != SOFT { return None; }
        Some(self.enter_method(path, SOFT, class, method, vec![Val::R(Some(id))]))
    }

    fn soft_referent(&mut self, path: &mut Path, id: usize) -> Step {
        self.keeps(path, Some(id), "observes possible clearing of a soft reference")?;
        if self.there_before(path, id) { self.reads(path, || "reads a soft referent".into())?; }
        let referent = path.objects[id].fields.get("referent").cloned()
            .ok_or_else(|| Stop::Unsupported("an unknown initial soft referent".into()))?;
        let old = self.gc_flag(path, id, CLEARED)?;
        let now = self.b.var();
        let cleared = self.b.or(old, now);
        let value = choose(&mut self.b, cleared, &Val::R(None), &referent)
            .ok_or_else(|| Stop::Unsupported("an unknown soft referent".into()))?;
        path.objects[id].fields.insert(CLEARED.into(), Val::I(self.b.zext(&vec![cleared], 32)));
        path.unbound_platform_value = Some(COLLECTION);
        self.push(path, value);
        self.advance(path);
        Ok(None)
    }
}
