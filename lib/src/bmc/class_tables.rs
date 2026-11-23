//! Order-independent folds over class mirrors in static lookup tables. The two accepted
//! bytecode loops write an inverse map and a name index, or index the union of an identity
//! map's values and primitive array classes. Each write is checked for commutativity at
//! the concrete key. The temporary iterator, entry and set must be dead at the exit.
//! Outstanding bucket order is never supplied to later users of a constructed table.
use super::*;
use crate::classfile::MemberRef;
use Insn::*;
use Kind::Ref;

const IDENTITY: &str = "java/util/IdentityHashMap";
const CLASS: &str = "java/lang/Class";
const MAP: &str = "java/util/Map";
const HASH: &str = "java/util/HashMap";
const SET: &str = "java/util/Set";
const SET_N: &str = "java/util/ImmutableCollections$SetN";
const ITER: &str = "java/util/Iterator";
const ENTRY: &str = "java/util/Map$Entry";
const OBJECT_RESULT: &str = "()Ljava/lang/Object;";
const PUT: &str = "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;";
pub(super) const TABLE: &str = "<JDK.unorderedClassTable>";
type Writes = BTreeMap<(usize, String), usize>;

fn member(cf: &ClassFile, index: u16, owner: &str, name: &str, descriptor: &str) -> bool {
    cf.pool.member(index).is_ok_and(|m| (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()) == (owner, name, descriptor))
}

fn static_map(path: &Path, cf: &ClassFile, index: u16, class: &str) -> Option<usize> {
    let f = cf.pool.member(index).ok()?;
    let field = cf.field(&f.name)?;
    if f.owner != cf.name || f.descriptor != "Ljava/util/Map;" || field.descriptor != f.descriptor
        || !field.is_static() || !field.is_final() { return None; }
    let &Val::R(Some(o)) = path.statics.get(&(f.owner, f.name))? else { return None };
    let obj = &path.objects[o];
    (obj.class == class && !obj.assumed && !obj.given && !obj.unknown).then_some(o)
}

// An enhanced for loop over an iterator. The body has its own straight-line shape below.
struct Traversal<'a> { body: &'a [Insn], element: u16, exit: usize }

fn traversal<'a>(f: &'a Frame, at: usize, element_type: &str) -> Option<Traversal<'a>> {
    let [InvokeInterface(iter), Store(Ref, it), Load(Ref, test), InvokeInterface(has), If(Cond::Eq, exit),
        Load(Ref, read), InvokeInterface(next), CheckCast(cast), Store(Ref, element), ..] = f.code.insns.get(at..)? else { return None };
    let exit = *f.code.index.get(exit)?;
    let back = exit.checked_sub(1)?;
    let cf = &f.class;
    if it != test || it != read || it == element || f.code.insns.get(back)? != &Goto(f.code.pcs[at + 2])
        || !member(cf, *iter, SET, "iterator", "()Ljava/util/Iterator;") || !member(cf, *has, ITER, "hasNext", "()Z")
        || !member(cf, *next, ITER, "next", OBJECT_RESULT) || cf.pool.class_name(*cast).ok()? != element_type
        || [*it, *element].iter().any(|&i| f.code.live[exit].get(usize::from(i)) != Some(&false)) { return None; }
    Some(Traversal { body: f.code.insns.get(at + 9..back)?, element: *element, exit })
}

// The complete body of map.put(mirror.getName(), mirror), with the old value discarded.
fn name_index(cf: &ClassFile, ops: &[Insn], local: u16) -> Option<u16> {
    let [GetStatic(map), Load(Ref, a), InvokeVirtual(name), Load(Ref, b), InvokeInterface(put), Pop] = ops else { return None };
    (*a == local && *b == local && member(cf, *name, CLASS, "getName", "()Ljava/lang/String;")
        && member(cf, *put, MAP, "put", PUT)).then_some(*map)
}

// A same-class static helper that does only the above put for each member of its argument array.
fn array_name_index(cf: &ClassFile, index: u16) -> Option<u16> {
    let call = cf.pool.member(index).ok()?;
    if call.owner != cf.name || call.descriptor != "([Ljava/lang/Class;)V" { return None; }
    let m = cf.method(&call.name, &call.descriptor)?;
    let code = m.code.as_ref()?;
    if !m.is_static() || !m.is_private() || m.access & crate::classfile::flags::SYNCHRONIZED != 0 || !code.exception_table.is_empty() { return None; }
    let insns = code.instructions().ok()?;
    let (pcs, ops): (Vec<_>, Vec<_>) = insns.into_iter().unzip();
    let [Load(Ref, 0), Store(Ref, 1), Load(Ref, 1), ArrayLength, Store(Kind::Int, 2), IConst(0), Store(Kind::Int, 3),
        Load(Kind::Int, 3), Load(Kind::Int, 2), IfICmp(Cond::Ge, end), Load(Ref, 1), Load(Kind::Int, 3), ArrayLoad(ArrayKind::Ref), Store(Ref, 4),
        .., IInc(3, 1), Goto(head), Return(None)] = ops.as_slice() else { return None };
    if *end != *pcs.last()? || *head != pcs[7] { return None; }
    name_index(cf, &ops[14..ops.len() - 3], 4)
}

fn inverse_indices(cf: &ClassFile, traversal: &Traversal<'_>) -> Option<(u16, u16)> {
    let [GetStatic(inverse), Load(Ref, a), InvokeInterface(value), CheckCast(v), Load(Ref, b), InvokeInterface(key), CheckCast(k),
        InvokeInterface(put), Pop, IConst(1), ANewArray(array), Dup, IConst(0), Load(Ref, c), InvokeInterface(key2), CheckCast(k2),
        ArrayStore(ArrayKind::Ref), InvokeStatic(helper)] = traversal.body else { return None };
    if [*a, *b, *c].iter().any(|&i| i != traversal.element)
        || [*v, *k, *k2, *array].iter().any(|&i| cf.pool.class_name(i).ok() != Some(CLASS))
        || !member(cf, *value, ENTRY, "getValue", OBJECT_RESULT) || !member(cf, *key, ENTRY, "getKey", OBJECT_RESULT)
        || !member(cf, *key2, ENTRY, "getKey", OBJECT_RESULT) || !member(cf, *put, MAP, "put", PUT) { return None; }
    Some((*inverse, array_name_index(cf, *helper)?))
}

fn record(writes: &mut Writes, map: usize, key: String, value: usize) -> Option<()> {
    // A repeated key is safe only when every possible last writer supplies the same reference.
    match writes.insert((map, key), value) { Some(old) if old != value => None, _ => Some(()) }
}

fn mirror(path: &Path, o: usize) -> Option<&Literal> {
    path.literals.iter().find_map(|(k, &v)| (v == o && matches!(k, Literal::Class(_) | Literal::PrimitiveClass(_))).then_some(k))
}

fn mirror_key(literal: &Literal) -> Option<String> {
    match literal {
        Literal::PrimitiveClass(d) => Some(format!("<key/primitive>{d}")),
        Literal::Class(c) => Some(format!("<key/class>{c}")),
        _ => None,
    }
}

fn name_key(literal: &Literal) -> Option<String> {
    let name = match literal {
        Literal::PrimitiveClass(d) => Type::parse(d).ok()?.java_name(),
        Literal::Class(c) => c.replace('/', "."),
        _ => return None,
    };
    Some(observed::lookup_key(Some(&name.encode_utf16().collect::<Vec<_>>())))
}

impl Engine<'_> {
    fn identity_class_entries(&self, path: &Path, o: usize) -> Option<Vec<(usize, usize)>> {
        let obj = &path.objects[o];
        let Some(Val::I(size)) = obj.fields.get("size") else { return None };
        let size = usize::try_from(self.b.constant_value(size)?).ok()?;
        if size == 0 || size > 128 || size > self.unwind as usize { return None; }
        let mut next = obj.fields.get("first")?;
        let mut entries = Vec::with_capacity(size);
        while let Val::R(Some(node)) = next {
            let binding = &path.objects[*node];
            if entries.len() == size || binding.class != "java/util/IdentityHashMap$Binding" { return None; }
            let (&Val::R(Some(key)), &Val::R(Some(value))) = (binding.fields.get("key")?, binding.fields.get("value")?) else { return None };
            mirror(path, key)?;
            mirror(path, value)?;
            entries.push((key, value));
            next = binding.fields.get("next")?;
        }
        (matches!(next, Val::R(None)) && entries.len() == size).then_some(entries)
    }

    fn inverse_fold(&self, path: &Path, f: &Frame) -> Option<(Writes, usize)> {
        let cf = &f.class;
        let [GetStatic(source), InvokeInterface(view), ..] = f.code.insns.get(f.at..)? else { return None };
        if !member(cf, *view, MAP, "entrySet", "()Ljava/util/Set;") { return None; }
        let t = traversal(f, f.at + 2, ENTRY)?;
        let (inverse, names) = inverse_indices(cf, &t)?;
        let source = static_map(path, cf, *source, IDENTITY)?;
        let inverse = static_map(path, cf, inverse, IDENTITY)?;
        let names = static_map(path, cf, names, HASH)?;
        if inverse == source || !path.objects[inverse].fields.is_empty() || !path.objects[names].fields.is_empty() { return None; }
        let mut writes = Writes::new();
        for (key, value) in self.identity_class_entries(path, source)? {
            record(&mut writes, inverse, mirror_key(mirror(path, value)?)?, key)?;
            record(&mut writes, names, name_key(mirror(path, key)?)?, key)?;
        }
        Some((writes, t.exit))
    }

    // The set is freshly allocated here, remains in one local, and is dead on exit.
    // Its contents are exactly the union. Hash collisions and either iteration order
    // have no effect on membership for Class mirrors (Object.equals is identity).
    fn value_union_fold(&mut self, path: &mut Path, f: &Frame) -> Option<(Writes, usize)> {
        let cf = &f.class;
        let ops = f.code.insns.get(f.at..)?;
        let [New(set), Dup, IConst(cap), InvokeSpecial(init), Store(Ref, local), Load(Ref, a), GetStatic(source),
            InvokeInterface(values), InvokeInterface(add), Pop, Load(Ref, b), IConst(count), ANewArray(array), tail @ ..] = ops else { return None };
        if !(0..=256).contains(cap) || !(0..=128).contains(count) || a != local || b != local || cf.pool.class_name(*set).ok()? != "java/util/HashSet"
            || !member(cf, *init, "java/util/HashSet", "<init>", "(I)V") || cf.pool.class_name(*array).ok()? != CLASS
            || !member(cf, *values, MAP, "values", "()Ljava/util/Collection;") || !member(cf, *add, SET, "addAll", "(Ljava/util/Collection;)Z") { return None; }
        let (cells, rest) = tail.split_at_checked(*count as usize * 4)?;
        let [InvokeStatic(add), Pop, Load(Ref, c), ..] = rest else { return None };
        if c != local || !member(cf, *add, "java/util/Collections", "addAll", "(Ljava/util/Collection;[Ljava/lang/Object;)Z") { return None; }
        let t = traversal(f, f.at + 13+cells.len() + 3, CLASS)?;
        let dest = static_map(path, cf, name_index(cf, t.body, t.element)?, HASH)?;
        if f.code.live[t.exit].get(usize::from(*local)) != Some(&false) || !path.objects[dest].fields.is_empty() { return None; }
        let source = static_map(path, cf, *source, IDENTITY)?;
        let entries = self.identity_class_entries(path, source)?;
        let mut arrays = Vec::new();
        for (i, cell) in cells.chunks_exact(4).enumerate() {
            let [Dup, IConst(index), Ldc(class), ArrayStore(ArrayKind::Ref)] = cell else { return None };
            let name = cf.pool.class_name(*class).ok()?;
            if *index != i as i32 || !matches!(Type::parse(name).ok()?, Type::Array(ty) if ty.is_primitive()) { return None; }
            arrays.push(name);
        }
        let mut writes = Writes::new();
        for (_, value) in entries { record(&mut writes, dest, name_key(mirror(path, value)?)?, value)?; }
        for name in arrays {
            let key = Literal::Class(name.to_string());
            let field = name_key(&key)?;
            let value = self.literal(path, key, CLASS);
            record(&mut writes, dest, field, value)?;
        }
        Some((writes, t.exit))
    }

    pub(super) fn fold_class_tables(&mut self, path: &mut Path) -> Option<Step> {
        let f = path.frames.last()?;
        if f.initializes.as_deref() != Some(&f.class.name) || !f.stack.is_empty() || !f.code.handlers.is_empty()
            || !self.cp.is_application(&f.class.name) || self.gap_mode != GapMode::Strict
            || self.cp.runs_model("java/util/HashSet") || self.previous.is_some() || !self.contracts.is_empty() || !self.observed.is_empty() || self.pure.is_some() || self.frame.is_some()
            || !self.summaries.is_empty() || !self.effects.is_empty() || !self.stand_ins.is_empty() { return None; }
        let ops = &f.code.insns[f.at..];
        let writes = match ops {
            [GetStatic(_), InvokeInterface(i), ..] if member(&f.class, *i, MAP, "entrySet", "()Ljava/util/Set;") && self.cp.class_table_image() => self.inverse_fold(path, f)?,
            [New(i), Dup, IConst(_), InvokeSpecial(_), Store(Ref, _), Load(Ref, _), GetStatic(_), InvokeInterface(_), ..]
                if f.class.pool.class_name(*i).ok() == Some("java/util/HashSet") && self.cp.class_table_image() => {
                let frame = f.clone();
                self.value_union_fold(path, &frame)?
            }
            _ => return None,
        };
        for ((map, key), value) in writes.0 {
            let fields = &mut path.objects[map].fields;
            fields.insert(TABLE.into(), Val::I(self.b.constant(1, 32)));
            fields.insert(key, Val::R(Some(value)));
        }
        path.frames.last_mut()?.at = writes.1;
        Some(Ok(None))
    }

    pub(super) fn class_set_constructor(&mut self, path: &mut Path, o: usize, m: &MemberRef, args: &[Val]) -> Option<Step> {
        if m.owner != SET_N || m.name != "<init>" || m.descriptor != "([Ljava/lang/Object;)V" || path.objects[o].class != SET_N
            || self.gap_mode != GapMode::Strict || !self.contracts.is_empty() || path.objects[o].given || path.objects[o].assumed || !self.cp.class_table_image() { return None; }
        let [Val::R(Some(a))] = args else { return None };
        let array = path.objects[*a].as_array()?;
        let size = array.refs.len();
        if !(3..=128).contains(&size) || self.b.constant_value(&array.length) != Some(size as i64) { return None; }
        let mut keys = BTreeMap::new();
        for item in &array.refs {
            let Val::R(Some(k)) = item else { return None };
            if keys.insert(mirror_key(mirror(path, *k)?)?, item.clone()).is_some() { return None; }
        }
        // SetN's 2*n slots always have an empty one in this range, even if every
        // identity hash collides. Only membership and size can observe the result.
        if self.there_before(path, *a) { if let Err(stop) = self.reads(path, || "reads class mirrors from the Set.of argument".into()) { return Some(Err(stop)); } }
        if let Err(stop) = self.keeps(path, Some(o), "constructs an immutable set of classes") { return Some(Err(stop)); }
        keys.insert(TABLE.into(), Val::I(self.b.constant(1, 32)));
        path.objects[o].fields.extend(keys);
        self.advance(path);
        Some(Ok(None))
    }

    pub(super) fn class_table_call(&mut self, path: &mut Path, o: usize, m: &MemberRef, args: &[Val], special: bool) -> Step {
        let class = path.objects[o].class.as_str();
        if special || !self.cp.is_subtype(class, &m.owner) { return unsupported("incompatible call on a class lookup table"); }
        if self.there_before(path, o) { self.reads(path, || "reads a class lookup table".into())?; }
        let result = match (m.name.as_str(), m.descriptor.as_str(), args) {
            (name @ ("size" | "isEmpty"), desc, []) if (name, desc) == ("size", "()I") || (name, desc) == ("isEmpty", "()Z") => {
                let size = path.objects[o].fields.keys().filter(|k| k.starts_with("<key/")).count() as i64;
                Val::I(self.b.constant(if name == "size" { size } else { i64::from(size == 0) }, 32))
            }
            ("get", "(Ljava/lang/Object;)Ljava/lang/Object;", [key]) | ("containsKey" | "contains", "(Ljava/lang/Object;)Z", [key])
            | ("put", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;", [key, _]) => {
                if (class == SET_N) != (m.name == "contains") { return unsupported("different collection operation on a class table"); }
                let field = match key {
                    Val::R(None) if class != SET_N => observed::lookup_key(None),
                    Val::R(Some(k)) if class == HASH && path.objects[*k].class == STRING => {
                        let Some(units) = self.constant_units(path, *k) else { return unsupported("a symbolic class name on a class lookup table") };
                        observed::lookup_key(Some(&units))
                    }
                    Val::R(Some(k)) if class != HASH => {
                        let Some(key) = mirror(path, *k).and_then(mirror_key) else { return unsupported("a non-mirror key on a class table") };
                        key
                    }
                    _ => return unsupported("a class lookup key outside the concrete mirror or name domain"),
                };
                let prior = path.objects[o].fields.get(&field).cloned();
                if let [_, value] = args {
                    self.keeps(path, Some(o), "updates a class lookup table")?;
                    path.objects[o].fields.insert(field, value.clone());
                }
                if m.name.starts_with("contains") { Val::I(self.b.constant(i64::from(prior.is_some()), 32)) } else { prior.unwrap_or(Val::R(None)) }
            }
            _ => return unsupported(format!("{}.{}{} is outside the unordered class lookup table", class.replace('/', "."), m.name, m.descriptor)),
        };
        self.push(path, result);
        self.advance(path);
        Ok(None)
    }
}
