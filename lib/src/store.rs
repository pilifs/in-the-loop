//! The stored types of a boundary contract: the shape of every Spring Data MongoDB document the module keeps, and
//! the field names the module's queries, updates, indexes, sorts and projections use, checked against those
//! shapes. A `Criteria.where("expiresAt")`, an `Update.set("status", ...)`, an `Index().on("holdId", ASC)`, a
//! `Sort.by("createdAt")` or a repository `@Query("{ 'customerId': ?0 }")` names a field as a string, and nothing
//! checks the string: the driver sends it to the database, which matches, writes, indexes or sorts by whatever
//! field that is, present or not. So a renamed record component leaves every query of it matching nothing,
//! every update of it writing a field nothing reads back, and every test that goes through the same strings
//! passing. The contract writes the stored shape of each document out (the `_id`, each field under its stored
//! name, the embedded types) and, under the document, a `!` line for every string that names a field the
//! document does not have.
//!
//! The shape follows the mapping layer: every non-static, non-transient field of the class and its superclasses
//! is a property, the `@Id` (or the property named `id`) is stored as `_id`, `@Field` renames, `@Transient` skips,
//! a record's components are its fields, and an embedded type's fields are reachable by a dotted path. A query
//! string may name a property by its Java name or its stored name, as the query mapper accepts both; a path goes
//! through collections and arrays to the element type, through a map to any key, and stops at a leaf (a string,
//! a date, an enum, a number), which has no fields.
//!
//! Which document a string is about is the document class the method mentions: the `SeatDocument.class` it
//! passes to the template, or the document it instantiates. A helper that builds a query or an update without
//! naming the document (a `private static Update makeAvailable()`) takes the documents of the methods that call
//! it; a string in a method with none of either is checked against every document of the module.

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::rc::Rc;

use crate::boundaries::{jump_targets, pushing, render_all, Bean, Member};
use crate::classfile::{flags, signature, signature::Sig, simple_name_of, Annotation, ArrayKind, ClassFile, Constant, ElementValue, Insn, Method, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::wire;
use crate::Error;

const DOCUMENT: &str = "org/springframework/data/mongodb/core/mapping/Document";
const FIELD: &str = "org/springframework/data/mongodb/core/mapping/Field";
const MONGO_ID: &str = "org/springframework/data/mongodb/core/mapping/MongoId";
const ID: &str = "org/springframework/data/annotation/Id";
const TRANSIENT: &str = "org/springframework/data/annotation/Transient";
const CRITERIA: &str = "org/springframework/data/mongodb/core/query/Criteria";
const UPDATE: &str = "org/springframework/data/mongodb/core/query/Update";
const INDEX: &str = "org/springframework/data/mongodb/core/index/Index";
const SORT: &str = "org/springframework/data/domain/Sort";
const ORDER: &str = "org/springframework/data/domain/Sort$Order";
const PROJECTION: &str = "org/springframework/data/mongodb/core/query/Field";
const QUERY: &str = "org/springframework/data/mongodb/repository/Query";
const COMPOUND_INDEX: &str = "org/springframework/data/mongodb/core/index/CompoundIndex";
const COMPOUND_INDEXES: &str = "org/springframework/data/mongodb/core/index/CompoundIndexes";

/// The `Update` methods whose first argument names the field they write.
const WRITES: &[&str] = &["update", "set", "setOnInsert", "inc", "push", "addToSet", "currentDate", "currentTimestamp", "multiply", "max", "min", "bitwise"];
/// The `Update` methods whose first argument names the field they remove from or take out of.
const REMOVES: &[&str] = &["unset", "pop", "pull", "pullAll", "rename"];

// ---------------------------------------------------------------------------------------------------------------
// Shapes

/// One stored property of a class.
struct Property {
    name: String,
    stored: String,
    /// The type with simple names (`List<String>`).
    ty: String,
    /// The generic signature or the descriptor, for the classes it names.
    raw: String,
    sig: Option<Sig>,
    /// The Spring Data annotations shown on the line (`@Indexed`, `@Version`, `@DBRef`).
    annotations: Vec<Annotation>,
}

/// The stored shape of a class: a document (with its collection) or a type embedded in one.
struct Shape {
    kind: &'static str,
    collection: Option<String>,
    properties: Vec<Property>,
    id: Option<usize>,
}

impl Shape {
    /// The property a path segment names: `_id` is the id property, and any property answers to its Java name
    /// or its stored name.
    fn find(&self, segment: &str) -> Option<&Property> {
        if segment == "_id" {
            return self.id.map(|i| &self.properties[i]);
        }
        self.properties.iter().find(|p| p.name == segment || p.stored == segment)
    }

    /// The property whose name is nearest the segment, for a hint.
    fn nearest(&self, segment: &str) -> Option<String> {
        let mut candidates: Vec<(usize, &str)> = Vec::new();
        for (i, p) in self.properties.iter().enumerate() {
            let shown = if self.id == Some(i) { "_id" } else { p.stored.as_str() };
            candidates.push((distance(shown, segment), shown));
            if p.name != shown {
                candidates.push((distance(&p.name, segment), &p.name));
            }
        }
        candidates.into_iter().filter(|(d, c)| *d <= 2 || (*d <= 3 && c.len() > 8)).min().map(|(_, c)| c.to_string())
    }
}

fn is_data(a: &Annotation) -> bool {
    a.type_name.starts_with("org/springframework/data/")
}

fn document_annotation(class: &ClassFile) -> Option<Annotation> {
    class.annotations().ok()?.into_iter().find(|a| a.type_name == DOCUMENT)
}

/// The collection a `@Document` names, or the one Spring derives from the class name.
fn collection_of(class: &ClassFile, a: &Annotation) -> String {
    let named = a.strings("value").into_iter().chain(a.strings("collection")).find(|s| !s.is_empty());
    named.unwrap_or_else(|| {
        let simple = simple_name_of(&class.name);
        let simple = simple.rsplit('.').next().unwrap_or(&simple);
        let mut chars = simple.chars();
        match chars.next() {
            Some(c) => c.to_lowercase().collect::<String>() + chars.as_str(),
            None => String::new(),
        }
    })
}

/// What a path segment steps into after a property of this type.
enum Step {
    Class(String),
    /// A map: any key, then its value type.
    Map(Option<Sig>),
    /// A type with no fields (a string, a date, a number, a `java.*` value): the simple name.
    Leaf(String),
    Unknown,
}

fn step(sig: Option<&Sig>) -> Step {
    match sig {
        None => Step::Unknown,
        Some(Sig::Array(elem)) => step(Some(elem)),
        Some(Sig::Primitive(c)) => Step::Leaf(Type::parse(&c.to_string()).map(|t| t.simple_name()).unwrap_or_else(|_| c.to_string())),
        Some(Sig::Wildcard(Some((_, bound)))) => step(Some(bound)),
        Some(Sig::Wildcard(None)) | Some(Sig::Variable(_)) => Step::Unknown,
        Some(Sig::Class { name, args }) => {
            let simple = simple_name_of(name);
            match name.as_str() {
                "java/util/Map" | "java/util/SortedMap" | "java/util/NavigableMap" | "java/util/HashMap" | "java/util/TreeMap" | "java/util/LinkedHashMap" | "java/util/concurrent/ConcurrentMap" => Step::Map(args.get(1).cloned()),
                "java/util/Optional" => step(args.first()),
                _ if name.starts_with("java/util/") && args.len() == 1 => step(args.first()),
                _ if name.starts_with("java/") || name.starts_with("org/bson/") => Step::Leaf(simple),
                _ => Step::Class(name.clone()),
            }
        }
    }
}

/// Why a path does not fit a shape.
struct Miss {
    /// The type the missing segment was looked for on.
    on: String,
    segment: String,
    hint: Option<String>,
    /// The type is a leaf: the segment is a field of something that has none.
    leaf: bool,
}

struct Shapes<'a> {
    cp: &'a ClassPath,
    cache: BTreeMap<String, Option<Rc<Shape>>>,
}

impl Shapes<'_> {
    /// The stored shape of a class on the class path (not of a JDK class); `None` when it cannot be read.
    fn shape(&mut self, name: &str) -> Option<Rc<Shape>> {
        if let Some(cached) = self.cache.get(name) {
            return cached.clone();
        }
        self.cache.insert(name.to_string(), None);
        let class = self.cp.load(name).ok().flatten().map(|l| l.class)?;
        let shape = Rc::new(self.build(&class));
        self.cache.insert(name.to_string(), Some(shape.clone()));
        Some(shape)
    }

    fn build(&self, class: &ClassFile) -> Shape {
        let kind = if class.is_record() {
            "record"
        } else if class.is_enum() {
            "enum"
        } else if class.is_interface() {
            "interface"
        } else {
            "class"
        };
        let collection = document_annotation(class).map(|a| collection_of(class, &a));
        // The superclasses' fields first, as the mapping layer walks them, without the JDK's.
        let mut chain: Vec<Rc<ClassFile>> = Vec::new();
        let mut sup = class.super_class.clone();
        while let Some(name) = sup.filter(|s| !s.starts_with("java/")) {
            let Some(c) = self.cp.load(&name).ok().flatten().map(|l| l.class) else { break };
            sup = c.super_class.clone();
            chain.push(c);
        }
        chain.reverse();
        let mut properties: Vec<Property> = Vec::new();
        let mut id: Option<usize> = None;
        let mut named_id: Option<usize> = None;
        for owner in chain.iter().map(Rc::as_ref).chain(std::iter::once(class)) {
            for field in &owner.fields {
                if field.is_static() || field.access & (flags::SYNTHETIC | flags::TRANSIENT) != 0 {
                    continue;
                }
                let annotations = field.annotations(&owner.pool).unwrap_or_default();
                if annotations.iter().any(|a| a.type_name == TRANSIENT) {
                    continue;
                }
                let raw = field.generic_signature(&owner.pool).unwrap_or_else(|| field.descriptor.clone());
                let stored = annotations.iter().find(|a| a.type_name == FIELD).and_then(|a| a.strings("value").into_iter().chain(a.strings("name")).find(|s| !s.is_empty())).unwrap_or_else(|| field.name.clone());
                let index = properties.len();
                if annotations.iter().any(|a| a.type_name == ID || a.type_name == MONGO_ID) {
                    id.get_or_insert(index);
                } else if field.name == "id" || field.name == "_id" {
                    named_id.get_or_insert(index);
                }
                properties.push(Property {
                    name: field.name.clone(),
                    stored,
                    ty: wire::field_type_name(owner, field),
                    sig: signature::parse_type(&raw),
                    raw,
                    annotations: annotations.into_iter().filter(|a| is_data(a) && !matches!(a.type_name.as_str(), ID | MONGO_ID | FIELD | TRANSIENT)).collect(),
                });
            }
        }
        let id = id.or(named_id);
        if let Some(i) = id {
            properties[i].stored = "_id".to_string();
        }
        Shape { kind, collection, properties, id }
    }

    /// Whether a dotted path names a field of the class, following embedded types; the miss says where it stops.
    fn resolve(&mut self, root: &str, path: &str) -> Result<(), Miss> {
        let mut current = Step::Class(root.to_string());
        for segment in path.split('.') {
            if segment.is_empty() || segment.starts_with('$') || segment.chars().all(|c| c.is_ascii_digit()) {
                continue;
            }
            current = match current {
                Step::Unknown => return Ok(()),
                Step::Map(value) => step(value.as_ref()),
                Step::Leaf(ty) => return Err(Miss { on: ty, segment: segment.to_string(), hint: None, leaf: true }),
                Step::Class(name) => {
                    let Some(shape) = self.shape(&name) else { return Ok(()) };
                    if shape.kind == "enum" {
                        return Err(Miss { on: simple_name_of(&name), segment: segment.to_string(), hint: None, leaf: true });
                    }
                    match shape.find(segment) {
                        Some(p) => step(p.sig.as_ref()),
                        None => return Err(Miss { on: simple_name_of(&name), segment: segment.to_string(), hint: shape.nearest(segment), leaf: false }),
                    }
                }
            };
        }
        Ok(())
    }
}

// ---------------------------------------------------------------------------------------------------------------
// Uses: the strings that name fields

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum Kind {
    Query,
    Write,
    Remove,
    Index,
    Sort,
    Projection,
}

impl Kind {
    fn verb(self) -> &'static str {
        match self {
            Kind::Query => "queries",
            Kind::Write => "writes",
            Kind::Remove => "removes",
            Kind::Index => "indexes",
            Kind::Sort => "sorts by",
            Kind::Projection => "projects",
        }
    }

    fn consequence(self) -> &'static str {
        match self {
            Kind::Query => "the condition tests a field that is never set",
            Kind::Write => "the update writes a field that nothing reads back",
            Kind::Remove => "the update changes nothing",
            Kind::Index => "the index is on a field that is never set",
            Kind::Sort => "the sort orders by a field that is never set",
            Kind::Projection => "the projection selects a field that is never set",
        }
    }
}

/// One string that names a field, where it is, and the documents it is about.
struct Use {
    kind: Kind,
    path: String,
    /// `TicketingStore.hold(String, List, String, Instant, Instant)`.
    site: String,
    class: String,
    line: Option<u16>,
    /// Document classes, internal names; empty when the site names none.
    scope: Vec<String>,
}

/// What one method mentions, before the scopes are resolved.
#[derive(Default)]
struct Mentions {
    /// The document classes the method names (a class literal, a `new`).
    documents: BTreeSet<String>,
    /// The methods of the same class it calls, by name and descriptor.
    calls: BTreeSet<(String, String)>,
    /// The field strings, with the instruction's pc.
    strings: Vec<(Kind, String, u32)>,
}

fn method_label(class: &ClassFile, method: &Method) -> String {
    let simple = simple_name_of(&class.name).replace('$', ".");
    let params = |d: &str| MethodDescriptor::parse(d).map(|d| d.params.iter().map(Type::simple_name).collect::<Vec<_>>().join(", ")).unwrap_or_default();
    if method.is_constructor() {
        return format!("{simple}({})", params(&method.descriptor));
    }
    if method.is_class_initializer() {
        return format!("the static initializer of {simple}");
    }
    if let Some(rest) = method.name.strip_prefix("lambda$") {
        if let Some((outer, _)) = rest.rsplit_once('$') {
            let outer_descriptor = class.methods.iter().find(|m| m.name == outer).map(|m| m.descriptor.clone()).unwrap_or_default();
            return format!("a lambda in {simple}.{outer}({})", params(&outer_descriptor));
        }
    }
    format!("{simple}.{}({})", method.name, params(&method.descriptor))
}

/// The string constant an instruction pushed, when it is one.
fn string_at(class: &ClassFile, insn: &Insn) -> Option<String> {
    match insn {
        Insn::Ldc(c) => match class.pool.get(*c).ok()? {
            Constant::String { string_index } => class.pool.utf8(*string_index).ok().map(str::to_string),
            _ => None,
        },
        _ => None,
    }
}

/// The strings stored into a `String[]` built just before the call at `call` (a varargs argument): each `ldc`
/// that an `aastore` follows, after the nearest `anewarray String` in the same basic block.
fn varargs(class: &ClassFile, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, call: usize) -> Vec<String> {
    let mut start = call;
    while start > 0 {
        if targets.contains(&insns[start].0) {
            return Vec::new();
        }
        start -= 1;
        if let Insn::ANewArray(c) = insns[start].1 {
            if class.pool.class_name(c).ok() == Some("java/lang/String") {
                break;
            }
        }
        if start == 0 {
            return Vec::new();
        }
    }
    let mut out = Vec::new();
    for i in start..call {
        if matches!(insns.get(i + 1).map(|(_, x)| x), Some(Insn::ArrayStore(ArrayKind::Ref))) {
            if let Some(s) = string_at(class, &insns[i].1) {
                out.push(s);
            }
        }
    }
    out
}

/// The field strings a call to the data API carries: the (kind, parameter index) pairs to read, with `None` for
/// a varargs parameter.
fn field_parameters(owner: &str, name: &str, descriptor: &str) -> Vec<(Kind, Option<usize>)> {
    let d = MethodDescriptor::parse(descriptor).ok();
    let last_is_varargs = d.as_ref().is_some_and(|d| matches!(d.params.last(), Some(Type::Array(inner)) if **inner == Type::Object("java/lang/String".to_string())));
    let first_string = |kind: Kind| d.as_ref().and_then(|d| d.params.iter().position(|p| *p == Type::Object("java/lang/String".to_string()))).map(|i| vec![(kind, Some(i))]).unwrap_or_default();
    match (owner, name) {
        (CRITERIA, "where" | "and" | "<init>") => first_string(Kind::Query),
        (UPDATE, n) if WRITES.contains(&n) => first_string(Kind::Write),
        (UPDATE, n) if REMOVES.contains(&n) => first_string(Kind::Remove),
        (INDEX, "on" | "<init>") => first_string(Kind::Index),
        (SORT, "by") if last_is_varargs => vec![(Kind::Sort, None)],
        (ORDER, "by" | "asc" | "desc" | "<init>") => first_string(Kind::Sort),
        (PROJECTION, "include" | "exclude") if last_is_varargs => vec![(Kind::Projection, None)],
        (PROJECTION, "include" | "exclude" | "slice" | "elemMatch" | "position") => first_string(Kind::Projection),
        _ => Vec::new(),
    }
}

fn mentions(class: &ClassFile, method: &Method, documents: &BTreeSet<String>) -> Mentions {
    let mut out = Mentions::default();
    let Some(code) = &method.code else { return out };
    let Ok(insns) = code.instructions() else { return out };
    let targets = jump_targets(&insns, method);
    for (i, (pc, insn)) in insns.iter().enumerate() {
        match insn {
            Insn::Ldc(c) => {
                if let Ok(Constant::Class { name_index }) = class.pool.get(*c) {
                    if let Ok(name) = class.pool.utf8(*name_index) {
                        if documents.contains(name) {
                            out.documents.insert(name.to_string());
                        }
                    }
                }
            }
            Insn::New(c) => {
                if let Ok(name) = class.pool.class_name(*c) {
                    if documents.contains(name) {
                        out.documents.insert(name.to_string());
                    }
                }
            }
            Insn::InvokeVirtual(idx) | Insn::InvokeSpecial(idx) | Insn::InvokeStatic(idx) | Insn::InvokeInterface(idx) => {
                let Ok(member) = class.pool.member(*idx) else { continue };
                if member.owner == class.name {
                    out.calls.insert((member.name.clone(), member.descriptor.clone()));
                }
                let Ok(d) = MethodDescriptor::parse(&member.descriptor) else { continue };
                let n = d.params.len();
                for (kind, param) in field_parameters(&member.owner, &member.name, &member.descriptor) {
                    match param {
                        None => out.strings.extend(varargs(class, &insns, &targets, i).into_iter().map(|s| (kind, s, *pc))),
                        Some(k) => {
                            if let Some(s) = pushing(class, &insns, &targets, i, n - 1 - k).and_then(|at| string_at(class, &insns[at].1)) {
                                out.strings.push((kind, s, *pc));
                            }
                        }
                    }
                }
            }
            _ => {}
        }
    }
    out
}

/// The field paths a repository `@Query` document (or its `sort` and `fields`) names: the keys of the JSON, with
/// the operators (`$and`, `$in`, `$elemMatch`) transparent and an embedded key under its parent's path.
pub(crate) fn json_keys(text: &str) -> Vec<String> {
    let chars: Vec<char> = text.chars().collect();
    let mut out = Vec::new();
    let mut pos = 0;
    if let Some(value) = parse_json(&chars, &mut pos) {
        collect_keys(&value, "", &mut out);
    }
    out
}

enum Json {
    Object(Vec<(String, Json)>),
    Array(Vec<Json>),
    Scalar,
}

fn skip_space(chars: &[char], pos: &mut usize) {
    while *pos < chars.len() && chars[*pos].is_whitespace() {
        *pos += 1;
    }
}

fn parse_json(chars: &[char], pos: &mut usize) -> Option<Json> {
    skip_space(chars, pos);
    match chars.get(*pos)? {
        '{' => {
            *pos += 1;
            let mut entries = Vec::new();
            loop {
                skip_space(chars, pos);
                match chars.get(*pos)? {
                    '}' => {
                        *pos += 1;
                        return Some(Json::Object(entries));
                    }
                    ',' => *pos += 1,
                    _ => {
                        let key = parse_key(chars, pos)?;
                        skip_space(chars, pos);
                        if chars.get(*pos) != Some(&':') {
                            return None;
                        }
                        *pos += 1;
                        let value = parse_json(chars, pos)?;
                        entries.push((key, value));
                    }
                }
            }
        }
        '[' => {
            *pos += 1;
            let mut items = Vec::new();
            loop {
                skip_space(chars, pos);
                match chars.get(*pos)? {
                    ']' => {
                        *pos += 1;
                        return Some(Json::Array(items));
                    }
                    ',' => *pos += 1,
                    _ => items.push(parse_json(chars, pos)?),
                }
            }
        }
        q @ ('\'' | '"') => {
            let q = *q;
            *pos += 1;
            while *pos < chars.len() && chars[*pos] != q {
                *pos += usize::from(chars[*pos] == '\\') + 1;
            }
            *pos += 1;
            Some(Json::Scalar)
        }
        _ => {
            // A number, a boolean, a placeholder (`?0`, `:#{...}`), a constructor call (`ObjectId('...')`): up
            // to the next separator outside parentheses.
            let mut depth = 0usize;
            while *pos < chars.len() {
                match chars[*pos] {
                    '(' | '{' | '[' => depth += 1,
                    ')' => depth = depth.saturating_sub(1),
                    '}' | ']' if depth > 0 => depth -= 1,
                    ',' | '}' | ']' => break,
                    _ => {}
                }
                *pos += 1;
            }
            Some(Json::Scalar)
        }
    }
}

fn parse_key(chars: &[char], pos: &mut usize) -> Option<String> {
    let mut key = String::new();
    match chars.get(*pos)? {
        q @ ('\'' | '"') => {
            let q = *q;
            *pos += 1;
            while *pos < chars.len() && chars[*pos] != q {
                key.push(chars[*pos]);
                *pos += 1;
            }
            *pos += 1;
        }
        _ => {
            while *pos < chars.len() && chars[*pos] != ':' && !chars[*pos].is_whitespace() {
                key.push(chars[*pos]);
                *pos += 1;
            }
        }
    }
    (!key.is_empty()).then_some(key)
}

fn collect_keys(value: &Json, prefix: &str, out: &mut Vec<String>) {
    match value {
        Json::Object(entries) => {
            for (key, value) in entries {
                if key.starts_with('$') {
                    collect_keys(value, prefix, out);
                } else {
                    let path = if prefix.is_empty() { key.clone() } else { format!("{prefix}.{key}") };
                    if !key.contains('?') && !key.contains('#') {
                        out.push(path.clone());
                    }
                    collect_keys(value, &path, out);
                }
            }
        }
        Json::Array(items) => items.iter().for_each(|v| collect_keys(v, prefix, out)),
        Json::Scalar => {}
    }
}

/// The top-level types of a class signature: the superclass, then the interfaces.
fn supertypes(signature: &str) -> Vec<Sig> {
    let b = signature.as_bytes();
    let mut i = 0;
    if b.first() == Some(&b'<') {
        let mut depth = 0;
        while i < b.len() {
            match b[i] {
                b'<' => depth += 1,
                b'>' => {
                    depth -= 1;
                    if depth == 0 {
                        i += 1;
                        break;
                    }
                }
                _ => {}
            }
            i += 1;
        }
    }
    let mut out = Vec::new();
    let mut start = i;
    let mut depth = 0;
    while i < b.len() {
        match b[i] {
            b'<' => depth += 1,
            b'>' => depth -= 1,
            b';' if depth == 0 => {
                out.extend(signature::parse_type(&signature[start..=i]));
                start = i + 1;
            }
            _ => {}
        }
        i += 1;
    }
    out
}

/// The domain type of a Spring Data repository interface: the first type argument of the `...Repository<T, ID>`
/// it extends, directly or through another local interface.
pub(crate) fn repository_domain(cp: &ClassPath, class: &ClassFile, depth: usize) -> Option<String> {
    if !class.is_interface() || depth > 3 {
        return None;
    }
    let signature = class.generic_signature()?;
    for sup in supertypes(&signature) {
        let Sig::Class { name, args } = &sup else { continue };
        if name.starts_with("org/springframework/data/") && name.ends_with("Repository") {
            if let Some(domain) = args.first().and_then(Sig::class_name) {
                return Some(domain.to_string());
            }
        }
    }
    for name in &class.interfaces {
        if let Some(sup) = cp.load(name).ok().flatten().map(|l| l.class) {
            if let Some(domain) = repository_domain(cp, &sup, depth + 1) {
                return Some(domain);
            }
        }
    }
    None
}

/// The uses in one class: the strings its methods pass to the data API, with their scopes, and the strings in
/// its `@Query` and `@CompoundIndex` annotations.
fn uses_in(cp: &ClassPath, class: &ClassFile, documents: &BTreeSet<String>) -> Vec<Use> {
    let mut out = Vec::new();
    let per_method: Vec<(&Method, Mentions)> = class.methods.iter().map(|m| (m, mentions(class, m, documents))).collect();
    for (method, found) in &per_method {
        if found.strings.is_empty() {
            continue;
        }
        let mut scope: Vec<String> = found.documents.iter().cloned().collect();
        if scope.is_empty() {
            // A helper that names no document: the documents of the methods that call it.
            let key = (method.name.clone(), method.descriptor.clone());
            let mut from_callers = BTreeSet::new();
            for (_, caller) in &per_method {
                if caller.calls.contains(&key) {
                    from_callers.extend(caller.documents.iter().cloned());
                }
            }
            scope = from_callers.into_iter().collect();
        }
        let site = method_label(class, method);
        let mut seen = BTreeSet::new();
        for (kind, path, pc) in &found.strings {
            if !seen.insert((*kind, path.clone())) {
                continue;
            }
            let line = method.code.as_ref().and_then(|c| c.line_at(*pc)).or(method.first_line());
            out.push(Use { kind: *kind, path: path.clone(), site: site.clone(), class: class.name.clone(), line, scope: scope.clone() });
        }
    }
    // The compound indexes a document declares.
    if documents.contains(&class.name) {
        let mut compound: Vec<Annotation> = Vec::new();
        for a in class.annotations().unwrap_or_default() {
            if a.type_name == COMPOUND_INDEX {
                compound.push(a);
            } else if a.type_name == COMPOUND_INDEXES {
                if let Some(ElementValue::Array(items)) = a.element("value") {
                    compound.extend(items.iter().filter_map(|v| match v {
                        ElementValue::Annotation(inner) => Some(inner.clone()),
                        _ => None,
                    }));
                }
            }
        }
        for a in compound {
            for def in a.strings("def") {
                for path in json_keys(&def) {
                    out.push(Use { kind: Kind::Index, path, site: format!("@CompoundIndex on {}", simple_name_of(&class.name)), class: class.name.clone(), line: None, scope: vec![class.name.clone()] });
                }
            }
        }
    }
    // The repository queries.
    if class.is_interface() {
        let domain = repository_domain(cp, class, 0);
        let scope: Vec<String> = domain.into_iter().filter(|d| documents.contains(d)).collect();
        for method in &class.methods {
            for a in method.annotations(&class.pool).unwrap_or_default() {
                if a.type_name != QUERY {
                    continue;
                }
                let site = format!("@Query on {}", method_label(class, method));
                for (element, kind) in [("value", Kind::Query), ("sort", Kind::Sort), ("fields", Kind::Projection)] {
                    for text in a.strings(element) {
                        for path in json_keys(&text) {
                            out.push(Use { kind, path, site: site.clone(), class: class.name.clone(), line: method.first_line(), scope: scope.clone() });
                        }
                    }
                }
            }
        }
    }
    out
}

// ---------------------------------------------------------------------------------------------------------------
// The blocks

fn distance(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    let mut previous: Vec<usize> = (0..=b.len()).collect();
    for i in 1..=a.len() {
        let mut current = vec![i; b.len() + 1];
        for j in 1..=b.len() {
            let cost = usize::from(a[i - 1] != b[j - 1]);
            current[j] = (previous[j] + 1).min(current[j - 1] + 1).min(previous[j - 1] + cost);
        }
        previous = current;
    }
    previous[b.len()]
}

fn member(line: String, problems: usize, source_line: Option<u16>, source_class: Option<String>) -> Member {
    Member { line, details: Vec::new(), entry: false, advised: false, problems, source_line, source_file: None, source_class }
}

/// The stored types of the module (`only`, or every application class): one block per `@Document` class and per
/// local type embedded in one, keyed by binary name with dots, with a `!` line under a document for each string
/// in the module's code that names a field it does not have.
pub fn analyse(cp: &ClassPath, only: Option<&BTreeSet<String>>, local: Option<&BTreeSet<String>>) -> Result<BTreeMap<String, Bean>, Error> {
    let in_module = |c: &str| only.is_none_or(|l| l.contains(c)) && cp.is_application(c);
    let is_local = |c: &str| local.is_none_or(|l| l.contains(c)) && cp.is_application(c);
    let classes = cp.application_classes()?;
    let documents: BTreeSet<String> = classes.iter().filter(|(n, c)| in_module(n) && c.access & flags::ANNOTATION == 0 && document_annotation(c).is_some()).map(|(n, _)| n.clone()).collect();
    let mut out = BTreeMap::new();
    if documents.is_empty() {
        return Ok(out);
    }
    let mut shapes = Shapes { cp, cache: BTreeMap::new() };

    // The shapes: the documents, then the local types their properties embed.
    let mut queue: VecDeque<String> = documents.iter().cloned().collect();
    let mut seen: BTreeSet<String> = BTreeSet::new();
    while let Some(name) = queue.pop_front() {
        if !seen.insert(name.clone()) {
            continue;
        }
        let Some(shape) = shapes.shape(&name) else { continue };
        if shape.kind == "enum" || shape.kind == "interface" {
            continue;
        }
        let header = match &shape.collection {
            Some(c) => format!("{}, collection \"{c}\"", shape.kind),
            None => format!("{}, embedded", shape.kind),
        };
        let mut members = Vec::new();
        for (i, p) in shape.properties.iter().enumerate() {
            let annotations = if p.annotations.is_empty() { String::new() } else { format!("{} ", render_all(&p.annotations)) };
            let origin = if shape.id == Some(i) || p.stored != p.name { format!(" ({})", p.name) } else { String::new() };
            members.push(member(format!("{}: {annotations}{}{origin}", p.stored, p.ty), 0, None, None));
            for referenced in wire::class_refs(&p.raw) {
                if is_local(&referenced) && !documents.contains(&referenced) {
                    queue.push_back(referenced);
                }
            }
        }
        if shape.id.is_none() && shape.collection.is_some() {
            members.push(member("_id: generated by the database, not a property of the class".to_string(), 0, None, None));
        }
        out.insert(name.replace('/', "."), Bean { annotations: header, members });
    }

    // The uses, checked against their scopes.
    let mut uses: Vec<Use> = Vec::new();
    for (name, class) in &classes {
        if !in_module(name) || class.access & (flags::ANNOTATION | flags::SYNTHETIC) != 0 {
            continue;
        }
        uses.extend(uses_in(cp, class, &documents));
    }
    let all: Vec<String> = documents.iter().cloned().collect();
    let mut problems: BTreeMap<String, Vec<(Option<u16>, String, Member)>> = BTreeMap::new();
    for u in uses {
        let scope: &[String] = if u.scope.is_empty() { &all } else { &u.scope };
        let mut misses: Vec<(String, Miss)> = Vec::new();
        for document in scope {
            match shapes.resolve(document, &u.path) {
                Ok(()) => {
                    misses.clear();
                    break;
                }
                Err(miss) => misses.push((document.clone(), miss)),
            }
        }
        if misses.is_empty() {
            continue;
        }
        // The document the line goes under: the one with a hint, else the first.
        let (document, miss) = misses.iter().find(|(_, m)| m.hint.is_some()).unwrap_or(&misses[0]);
        let named: Vec<String> = scope.iter().map(|d| simple_name_of(d)).collect();
        let on = if miss.leaf {
            format!("{} is a {}, which has no fields", if u.path == miss.segment { "it".to_string() } else { format!("\"{}\"", u.path[..u.path.rfind(&miss.segment).unwrap_or(0)].trim_end_matches('.')) }, miss.on)
        } else if u.scope.is_empty() {
            format!("not a field of any document in the module ({})", named.join(", "))
        } else if miss.segment == u.path {
            format!("not a field of {}", join_or(&named))
        } else {
            format!("\"{}\" is not a field of {}", miss.segment, miss.on)
        };
        let hint = miss.hint.as_ref().map(|h| format!(" ({h}?)")).unwrap_or_default();
        let line = format!("! {} {} \"{}\": {on}{hint}, so {}", u.site, u.kind.verb(), u.path, u.kind.consequence());
        problems.entry(document.clone()).or_default().push((u.line, u.path.clone(), member(line, 1, u.line, Some(u.class.clone()))));
    }
    for (document, mut found) in problems {
        found.sort_by(|a, b| (a.0, &a.1).cmp(&(b.0, &b.1)));
        if let Some(bean) = out.get_mut(&document.replace('/', ".")) {
            bean.members.extend(found.into_iter().map(|(_, _, m)| m));
        }
    }
    Ok(out)
}

fn join_or(names: &[String]) -> String {
    match names.len() {
        0 => String::new(),
        1 => names[0].clone(),
        n => format!("{} or {}", names[..n - 1].join(", "), names[n - 1]),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn query_documents_give_their_field_paths() {
        assert_eq!(json_keys("{ 'customerId': ?0, 'labels': { '$in': ?1 } }"), vec!["customerId", "labels"]);
        assert_eq!(json_keys("{ \"$and\": [ { \"a\": 1 }, { \"b.c\": { \"$gt\": 2 } } ] }"), vec!["a", "b.c"]);
        assert_eq!(json_keys("{ steps: { $elemMatch: { done: true } } }"), vec!["steps", "steps.done"]);
        assert_eq!(json_keys("{ 'created': -1 }"), vec!["created"]);
        assert_eq!(json_keys("{ '_id': ObjectId('abc'), 'when': { '$lt': :#{#now} } }"), vec!["_id", "when"]);
        assert!(json_keys("{ 'a': ").is_empty());
    }

    #[test]
    fn class_signatures_split_into_supertypes() {
        let found = supertypes("Ljava/lang/Object;Lorg/springframework/data/mongodb/repository/MongoRepository<Lnet/x/Note;Ljava/lang/String;>;");
        assert_eq!(found.len(), 2);
        assert_eq!(found[1].class_name(), Some("org/springframework/data/mongodb/repository/MongoRepository"));
        let Sig::Class { args, .. } = &found[1] else { panic!() };
        assert_eq!(args[0].class_name(), Some("net/x/Note"));
        let generic = supertypes("<T:Ljava/lang/Object;>Ljava/lang/Object;Ljava/util/List<TT;>;");
        assert_eq!(generic.len(), 2);
    }

    #[test]
    fn steps_follow_collections_and_stop_at_leaves() {
        assert!(matches!(step(signature::parse_type("Ljava/util/List<Lnet/x/Step;>;").as_ref()), Step::Class(c) if c == "net/x/Step"));
        assert!(matches!(step(signature::parse_type("[Lnet/x/Step;").as_ref()), Step::Class(_)));
        assert!(matches!(step(signature::parse_type("Ljava/util/Map<Ljava/lang/String;Ljava/lang/Integer;>;").as_ref()), Step::Map(Some(_))));
        assert!(matches!(step(signature::parse_type("Ljava/time/Instant;").as_ref()), Step::Leaf(t) if t == "Instant"));
        assert!(matches!(step(signature::parse_type("J").as_ref()), Step::Leaf(t) if t == "long"));
        assert!(matches!(step(signature::parse_type("TT;").as_ref()), Step::Unknown));
    }

    #[test]
    fn field_parameters_name_the_string_argument() {
        assert_eq!(field_parameters(CRITERIA, "where", "(Ljava/lang/String;)Lorg/springframework/data/mongodb/core/query/Criteria;"), vec![(Kind::Query, Some(0))]);
        assert_eq!(field_parameters(UPDATE, "set", "(Ljava/lang/String;Ljava/lang/Object;)Lorg/springframework/data/mongodb/core/query/Update;"), vec![(Kind::Write, Some(0))]);
        assert_eq!(field_parameters(SORT, "by", "(Lorg/springframework/data/domain/Sort$Direction;[Ljava/lang/String;)Lorg/springframework/data/domain/Sort;"), vec![(Kind::Sort, None)]);
        assert_eq!(field_parameters(ORDER, "<init>", "(Lorg/springframework/data/domain/Sort$Direction;Ljava/lang/String;)V"), vec![(Kind::Sort, Some(1))]);
        assert!(field_parameters(CRITERIA, "is", "(Ljava/lang/Object;)Lorg/springframework/data/mongodb/core/query/Criteria;").is_empty());
    }
}
