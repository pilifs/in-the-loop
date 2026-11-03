//! The wire section of a boundary contract: the JSON shape of every type that crosses the module's boundary. A
//! request or response body, or a message on a topic, is a Java type on one side and bytes on the other, and the
//! bytes are what the other side depends on. Jackson derives the shape from the class (record components, public
//! getters and fields, enum constants) and its annotations (`@JsonProperty`, `@JsonIgnore`, `@JsonInclude`,
//! `@JsonNaming`, `@JsonTypeInfo` with `@JsonSubTypes`), so a renamed component, a dropped `@JsonSubTypes` entry or
//! a new enum constant changes the wire format without changing any signature, and every test that encodes and
//! decodes with the same classes passes. The contract writes the shape out, one block per type reachable from the
//! module's handlers, listeners and Jackson-annotated types, so that the diff is the wire change.
//!
//! The defaults are Jackson 3's as Spring Boot configures them, checked against the library: standard bean naming
//! (`getURL` is `URL`), `is` getters for `Boolean` as well as `boolean`, an empty `Optional` written as null, an
//! empty bean written as `{}`, and a subtype that `@JsonSubTypes` does not list written under its class name and
//! rejected when read back.

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::rc::Rc;

use crate::boundaries::{is_validation, render_all, Bean, Member};
use crate::classfile::{flags, signature, simple_name_of, Annotation, ClassFile, Field, Method, MethodDescriptor, Type, TypeAnnotation, TypeTarget};
use crate::classpath::{ClassPath, Origin};
use crate::validation;
use crate::Error;

pub fn is_jackson(a: &Annotation) -> bool {
    a.type_name.starts_with("com/fasterxml/jackson/") || a.type_name.starts_with("tools/jackson/")
}

/// A Spring Data or JPA mapping: a class with one is a storage shape.
fn persistence(a: &Annotation) -> Option<String> {
    let simple = a.simple_name();
    let data = a.type_name.starts_with("org/springframework/data/") && matches!(simple.as_str(), "Document" | "Table" | "RedisHash" | "Node");
    let jpa = (a.type_name.starts_with("jakarta/persistence/") || a.type_name.starts_with("javax/persistence/")) && simple == "Entity";
    (data || jpa).then(|| format!("@{simple}"))
}

/// The classes a descriptor or generic signature names, as internal names, in order of appearance.
pub fn class_refs(s: &str) -> Vec<String> {
    let b = s.as_bytes();
    let mut out = Vec::new();
    let mut i = 0;
    while i < b.len() {
        match b[i] {
            b'L' => {
                let start = i + 1;
                let mut j = start;
                while j < b.len() && !matches!(b[j], b'<' | b';' | b'.') {
                    j += 1;
                }
                out.push(String::from_utf8_lossy(&b[start..j]).into_owned());
                i = j;
            }
            // A type variable, or the inner class after an outer's type arguments: not a class name.
            b'T' | b'.' => {
                let mut j = i + 1;
                while j < b.len() && !matches!(b[j], b';' | b'<') {
                    j += 1;
                }
                i = j;
            }
            _ => i += 1,
        }
    }
    out
}

/// Jackson's default type id: the name after the last `.`, so a nested class keeps its outer class (`Outer$Inner`).
fn default_type_id(internal: &str) -> String {
    internal.rsplit('/').next().unwrap_or(internal).to_string()
}

/// Java Beans decapitalisation, which Jackson 3 uses: `getURL` is `URL`, `getCustomerName` is `customerName`.
fn decapitalize(s: &str) -> String {
    let chars: Vec<char> = s.chars().collect();
    if chars.len() >= 2 && chars[0].is_uppercase() && chars[1].is_uppercase() {
        return s.to_string();
    }
    let mut out: String = chars.first().map(|c| c.to_lowercase().collect()).unwrap_or_default();
    out.extend(chars.iter().skip(1));
    out
}

/// Jackson's `SnakeCaseStrategy` with the separator as given: `customerName` is `customer_name`, `URL` is `url`.
fn separated(name: &str, sep: char) -> String {
    let mut out = String::new();
    let mut previous_translated = false;
    for c in name.chars() {
        if c.is_uppercase() {
            if !previous_translated && !out.is_empty() && !out.ends_with(sep) {
                out.push(sep);
            }
            out.extend(c.to_lowercase());
            previous_translated = true;
        } else {
            out.push(c);
            previous_translated = false;
        }
    }
    out
}

/// A property's wire name under a `@JsonNaming` strategy, by the strategy class's simple name.
fn renamed(strategy: &str, name: &str) -> String {
    match strategy {
        "SnakeCaseStrategy" => separated(name, '_'),
        "UpperSnakeCaseStrategy" => separated(name, '_').to_uppercase(),
        "KebabCaseStrategy" => separated(name, '-'),
        "LowerDotCaseStrategy" => separated(name, '.'),
        "LowerCaseStrategy" => name.to_lowercase(),
        "UpperCamelCaseStrategy" => {
            let mut chars = name.chars();
            chars.next().map(|c| c.to_uppercase().chain(chars).collect()).unwrap_or_default()
        }
        _ => name.to_string(),
    }
}

/// The field's type as a reader of the source would see it.
pub fn field_type_name(class: &ClassFile, field: &Field) -> String {
    field.generic_signature(&class.pool).and_then(|s| signature::field_type(&s)).or_else(|| Type::parse(&field.descriptor).ok().map(|t| t.simple_name())).unwrap_or_else(|| field.descriptor.clone())
}

fn return_type_name(class: &ClassFile, method: &Method) -> String {
    if let Some((_, ret)) = method.generic_signature(&class.pool).and_then(|s| signature::method_types(&s)) {
        return ret;
    }
    MethodDescriptor::parse(&method.descriptor).map(|d| d.ret.simple_name()).unwrap_or_default()
}

fn parameter_type_names(class: &ClassFile, method: &Method) -> Vec<String> {
    let d = MethodDescriptor::parse(&method.descriptor).ok();
    if let Some((params, _)) = method.generic_signature(&class.pool).and_then(|s| signature::method_types(&s)) {
        if d.as_ref().is_none_or(|d| d.params.len() == params.len()) {
            return params;
        }
    }
    d.map(|d| d.params.iter().map(Type::simple_name).collect()).unwrap_or_default()
}

/// The classes the method's parameter types and return type name: the raw signature when it has one, else the
/// descriptor.
pub fn method_refs(class: &ClassFile, method: &Method) -> (Vec<Vec<String>>, Vec<String>) {
    let count = MethodDescriptor::parse(&method.descriptor).map(|d| d.params.len()).unwrap_or(0);
    if let Some((params, ret)) = method.generic_signature(&class.pool).and_then(|s| signature::method_parts(&s)) {
        if params.len() == count {
            return (params.iter().map(|p| class_refs(p)).collect(), class_refs(&ret));
        }
    }
    match signature::method_parts(&method.descriptor) {
        Some((params, ret)) => (params.iter().map(|p| class_refs(p)).collect(), class_refs(&ret)),
        None => (vec![Vec::new(); count], Vec::new()),
    }
}

/// `Optional<T>` is `T` that may be null; everything else is itself.
fn unwrap_optional(rendered: &str) -> (String, bool) {
    if let Some(inner) = rendered.strip_prefix("Optional<").and_then(|r| r.strip_suffix('>')) {
        return (inner.to_string(), true);
    }
    match rendered {
        "OptionalInt" => ("int".to_string(), true),
        "OptionalLong" => ("long".to_string(), true),
        "OptionalDouble" => ("double".to_string(), true),
        _ => (rendered.to_string(), false),
    }
}

fn is_primitive(rendered: &str) -> bool {
    matches!(rendered, "boolean" | "byte" | "char" | "short" | "int" | "long" | "float" | "double")
}

/// An `@JsonInclude` value that leaves a property out of the JSON for some of its values.
fn omits(include: &Annotation) -> Option<bool> {
    let value = include.enum_names("value").into_iter().next()?;
    match value.as_str() {
        "ALWAYS" | "USE_DEFAULTS" => None,
        "NON_DEFAULT" => Some(true),
        _ => Some(false),
    }
}

/// How Jackson names the subtype of a polymorphic type: from `@JsonTypeInfo` on the base.
struct TypeInfo {
    base: String,
    use_: String,
    include: String,
    property: String,
}

impl TypeInfo {
    fn from(base: &str, a: &Annotation) -> TypeInfo {
        let use_ = a.enum_names("use").into_iter().next().unwrap_or_else(|| "NONE".to_string());
        let include = a.enum_names("include").into_iter().next().unwrap_or_else(|| "PROPERTY".to_string());
        let mut property = a.strings("property").into_iter().next().unwrap_or_default();
        if property.is_empty() {
            property = match use_.as_str() {
                "CLASS" => "@class",
                "MINIMAL_CLASS" => "@c",
                _ => "@type",
            }
            .to_string();
        }
        TypeInfo { base: base.to_string(), use_, include, property }
    }

    fn describe(&self) -> Option<String> {
        let what = match self.use_.as_str() {
            "NAME" | "SIMPLE_NAME" => "names the subtype",
            "CLASS" | "MINIMAL_CLASS" => "names the subtype's Java class",
            "DEDUCTION" => return Some("the subtype is deduced from the properties".to_string()),
            _ => return None,
        };
        let placement = match self.include.as_str() {
            "PROPERTY" | "EXISTING_PROPERTY" => format!("\"{}\" {what}", self.property),
            "WRAPPER_OBJECT" => format!("the one key of a wrapping object {what}"),
            "WRAPPER_ARRAY" => format!("the first element of a wrapping array {what}"),
            "EXTERNAL_PROPERTY" => format!("\"{}\" of the enclosing object {what}", self.property),
            other => format!("{other}: \"{}\" {what}", self.property),
        };
        Some(placement)
    }
}

pub(crate) struct Prop {
    pub(crate) implicit: String,
    explicit: Option<String>,
    ty: Option<String>,
    /// The type's generic signature, or its descriptor: what the constraints are checked against.
    signature: Option<String>,
    creates: bool,
    ignored: bool,
    /// The validation annotations on the property itself (`@NotBlank`, `@Valid`).
    pub(crate) constraints: Vec<Annotation>,
    /// The validation annotations inside the type (`List<@NotBlank String>`), with their paths.
    pub(crate) type_constraints: Vec<TypeAnnotation>,
    details: Vec<Annotation>,
    include: Option<Annotation>,
    source_line: Option<u16>,
}

impl Prop {
    fn new(implicit: &str) -> Prop {
        Prop { implicit: implicit.to_string(), explicit: None, ty: None, signature: None, creates: false, ignored: false, constraints: Vec::new(), type_constraints: Vec::new(), details: Vec::new(), include: None, source_line: None }
    }

    /// Takes in the type annotations of one accessor: those on the target's type, below its top (the top-level
    /// ones repeat the declaration annotations).
    fn absorb_typed(&mut self, annotations: &[TypeAnnotation], target: &TypeTarget) {
        for t in annotations.iter().filter(|t| &t.target == target && !t.path.is_empty() && is_validation(&t.annotation)) {
            if !self.type_constraints.iter().any(|c| c.path == t.path && c.annotation.render() == t.annotation.render()) {
                self.type_constraints.push(t.clone());
            }
        }
    }

    /// Whether validation steps into the value: `@Valid` on the property or inside its type.
    pub(crate) fn cascades(&self) -> bool {
        self.constraints.iter().any(validation::is_valid) || self.type_constraints.iter().any(|t| validation::is_valid(&t.annotation))
    }

    /// The classes the type names, outermost first.
    pub(crate) fn referenced(&self) -> Vec<String> {
        self.signature.as_deref().map(class_refs).unwrap_or_default()
    }

    /// The type as written, with the constraints inside it written in.
    fn rendered_type(&self) -> String {
        let mut ty = self.ty.clone().unwrap_or_else(|| "?".to_string());
        for t in self.type_constraints.iter().rev() {
            ty = validation::annotate(&ty, &t.path, &t.annotation.render());
        }
        ty
    }

    /// The constraints that cannot run as written: on a type without a validator, a null check on a primitive.
    fn constraint_problems(&self, cp: &ClassPath) -> Vec<String> {
        let mut out = Vec::new();
        let Some(sig) = self.signature.as_deref().and_then(signature::parse_type) else { return out };
        for c in self.constraints.iter().filter(|c| validation::is_constraint(c)) {
            out.extend(validation::problem(cp, c, &sig));
        }
        for t in self.type_constraints.iter().filter(|t| validation::is_constraint(&t.annotation)) {
            if let Some(part) = sig.at(&t.path) {
                out.extend(validation::problem(cp, &t.annotation, part));
            }
        }
        out
    }

    /// Takes in the annotations of one accessor: the consumed ones set the name, ignoral and inclusion, the
    /// constraints go before the type, and the rest are details.
    fn absorb(&mut self, annotations: &[Annotation]) {
        for a in annotations {
            let simple = a.simple_name();
            if is_validation(a) {
                if !self.constraints.iter().any(|c| c.render() == a.render()) {
                    self.constraints.push(a.clone());
                }
                continue;
            }
            if !is_jackson(a) {
                continue;
            }
            match simple.as_str() {
                "JsonProperty" | "JsonGetter" | "JsonSetter" => {
                    let name = a.strings("value").into_iter().next().unwrap_or_default();
                    if !name.is_empty() {
                        self.explicit = Some(name);
                    } else if self.explicit.is_none() {
                        self.explicit = Some(self.implicit.clone());
                    }
                    self.creates = true;
                    if a.strings("access").is_empty() && a.enum_names("access").is_empty() {
                        continue;
                    }
                    self.details.push(a.clone());
                }
                "JsonIgnore" => self.ignored = a.element("value").is_none_or(|v| !matches!(v, crate::classfile::ElementValue::Boolean(false))),
                "JsonInclude" => self.include = Some(a.clone()),
                _ => {
                    if !self.details.iter().any(|d| d.render() == a.render()) {
                        self.details.push(a.clone());
                    }
                }
            }
        }
    }
}

struct Shape {
    header: Vec<String>,
    members: Vec<Member>,
    /// Types to render next: property types, subtypes, the base.
    next: Vec<String>,
}

fn member(line: String, details: Vec<String>, problems: usize, source_line: Option<u16>) -> Member {
    Member { line, details, entry: false, advised: false, problems, source_line, source_file: None, source_class: None }
}

fn problem(text: String) -> Member {
    member(format!("! {text}"), Vec::new(), 1, None)
}

/// Loads an application class that the closure may follow: on the class path, from the module's own build when
/// `local` says which those are.
pub(crate) fn local_class(cp: &ClassPath, local: Option<&BTreeSet<String>>, name: &str) -> Option<Rc<ClassFile>> {
    if local.is_some_and(|set| !set.contains(name)) {
        return None;
    }
    match cp.load(name).ok().flatten() {
        Some(loaded) if loaded.origin == Origin::Application => Some(loaded.class),
        _ => None,
    }
}

/// The nearest `@JsonTypeInfo` on the class or one of its supertypes, as Jackson looks it up.
fn type_info(cp: &ClassPath, local: Option<&BTreeSet<String>>, class: &ClassFile) -> Option<(TypeInfo, Rc<ClassFile>)> {
    let mut queue: VecDeque<Rc<ClassFile>> = VecDeque::new();
    let mut seen = BTreeSet::new();
    let own = Rc::new(class.clone());
    queue.push_back(own);
    while let Some(c) = queue.pop_front() {
        if !seen.insert(c.name.clone()) {
            continue;
        }
        if let Some(a) = c.annotations().ok()?.iter().find(|a| is_jackson(a) && a.simple_name() == "JsonTypeInfo") {
            return Some((TypeInfo::from(&c.name, a), c.clone()));
        }
        let mut supers: Vec<String> = c.super_class.iter().cloned().collect();
        supers.extend(c.interfaces.iter().cloned());
        for s in supers {
            if let Some(sc) = local_class(cp, local, &s) {
                queue.push_back(sc);
            }
        }
    }
    None
}

/// The registered subtypes of a base: (type id, internal name) from `@JsonSubTypes`, and whether the annotation is
/// there at all.
fn registered_subtypes(base: &ClassFile) -> (bool, Vec<(Option<String>, String)>) {
    let annotations = base.annotations().unwrap_or_default();
    let Some(subtypes) = annotations.iter().find(|a| is_jackson(a) && a.simple_name() == "JsonSubTypes") else { return (false, Vec::new()) };
    let mut out = Vec::new();
    if let Some(crate::classfile::ElementValue::Array(items)) = subtypes.element("value") {
        for item in items {
            if let crate::classfile::ElementValue::Annotation(t) = item {
                let class = t.classes("value").into_iter().next();
                let mut names = t.strings("names");
                names.extend(t.strings("name"));
                let name = names.into_iter().find(|n| !n.is_empty());
                if let Some(class) = class {
                    out.push((name, class));
                }
            }
        }
    }
    (true, out)
}

fn type_name_of(class: &ClassFile) -> Option<String> {
    class.annotations().unwrap_or_default().iter().find(|a| is_jackson(a) && a.simple_name() == "JsonTypeName").and_then(|a| a.strings("value").into_iter().next()).filter(|n| !n.is_empty())
}

/// The properties of a class as Jackson finds them: record components; else public fields, public getters, setters
/// and `@JsonProperty` members, of the superclasses first.
pub(crate) fn properties(cp: &ClassPath, local: Option<&BTreeSet<String>>, class: &ClassFile) -> Vec<Prop> {
    let mut props: Vec<Prop> = Vec::new();
    fn prop<'a>(props: &'a mut Vec<Prop>, implicit: &str) -> &'a mut Prop {
        if let Some(i) = props.iter().position(|p| p.implicit == implicit) {
            return &mut props[i];
        }
        props.push(Prop::new(implicit));
        props.last_mut().expect("just pushed")
    }
    if class.is_record() {
        for component in class.record_components().unwrap_or_default() {
            let p = prop(&mut props, &component.name);
            p.creates = true;
            if let Some(field) = class.fields.iter().find(|f| f.name == component.name) {
                p.ty = Some(field_type_name(class, field));
                p.signature = Some(field.generic_signature(&class.pool).unwrap_or_else(|| field.descriptor.clone()));
                p.absorb(&field.annotations(&class.pool).unwrap_or_default());
                p.absorb_typed(&field.type_annotations(&class.pool).unwrap_or_default(), &TypeTarget::Field);
            }
            if let Some(accessor) = class.methods.iter().find(|m| m.name == component.name && m.descriptor.starts_with("()")) {
                p.absorb(&accessor.annotations(&class.pool).unwrap_or_default());
                p.absorb_typed(&accessor.type_annotations(&class.pool).unwrap_or_default(), &TypeTarget::Return);
                p.source_line = accessor.first_line();
            }
        }
        return props;
    }
    if let Some(sc) = class.super_class.as_deref().filter(|s| !s.starts_with("java/")).and_then(|s| local_class(cp, local, s)) {
        props = properties(cp, local, &sc);
    }
    for field in &class.fields {
        if field.is_static() || field.access & flags::SYNTHETIC != 0 {
            continue;
        }
        let annotations = field.annotations(&class.pool).unwrap_or_default();
        let p = prop(&mut props, &field.name);
        if field.access & flags::PUBLIC != 0 {
            p.creates = true;
        }
        if p.ty.is_none() || field.access & flags::PUBLIC != 0 {
            p.ty = Some(field_type_name(class, field));
            p.signature = Some(field.generic_signature(&class.pool).unwrap_or_else(|| field.descriptor.clone()));
        }
        p.absorb(&annotations);
        p.absorb_typed(&field.type_annotations(&class.pool).unwrap_or_default(), &TypeTarget::Field);
    }
    for method in &class.methods {
        if method.is_static() || method.is_synthetic() || method.is_bridge() || method.is_constructor() || method.is_class_initializer() {
            continue;
        }
        let annotations = method.annotations(&class.pool).unwrap_or_default();
        let explicit = annotations.iter().any(|a| is_jackson(a) && matches!(a.simple_name().as_str(), "JsonProperty" | "JsonGetter" | "JsonSetter"));
        let Ok(d) = MethodDescriptor::parse(&method.descriptor) else { continue };
        if d.params.is_empty() && d.ret != Type::Void {
            let implicit = if let Some(rest) = method.name.strip_prefix("get").filter(|r| !r.is_empty()) {
                Some(decapitalize(rest))
            } else if let Some(rest) = method.name.strip_prefix("is").filter(|r| !r.is_empty() && (d.ret == Type::Boolean || d.ret == Type::Object("java/lang/Boolean".into()))) {
                Some(decapitalize(rest))
            } else {
                None
            };
            let getter = implicit.is_some() && method.is_public();
            if !getter && !explicit {
                continue;
            }
            let implicit = implicit.unwrap_or_else(|| method.name.clone());
            let p = prop(&mut props, &implicit);
            p.creates |= getter;
            p.ty = Some(return_type_name(class, method));
            p.signature = method.generic_signature(&class.pool).and_then(|s| signature::method_parts(&s)).or_else(|| signature::method_parts(&method.descriptor)).map(|(_, ret)| ret);
            p.source_line = p.source_line.or(method.first_line());
            p.absorb(&annotations);
            p.absorb_typed(&method.type_annotations(&class.pool).unwrap_or_default(), &TypeTarget::Return);
        } else if d.params.len() == 1 && d.ret == Type::Void {
            let implicit = method.name.strip_prefix("set").filter(|r| !r.is_empty()).map(decapitalize);
            if implicit.is_none() && !explicit {
                continue;
            }
            let implicit = implicit.unwrap_or_else(|| method.name.clone());
            let p = prop(&mut props, &implicit);
            p.creates = true;
            if p.ty.is_none() {
                p.ty = parameter_type_names(class, method).into_iter().next();
                p.signature = method.generic_signature(&class.pool).and_then(|s| signature::method_parts(&s)).or_else(|| signature::method_parts(&method.descriptor)).and_then(|(params, _)| params.into_iter().next());
            }
            p.absorb(&annotations);
            p.absorb_typed(&method.type_annotations(&class.pool).unwrap_or_default(), &TypeTarget::Parameter(0));
        } else if explicit {
            let p = prop(&mut props, &method.name);
            p.absorb(&annotations);
        }
    }
    props
}

fn shape(cp: &ClassPath, local: Option<&BTreeSet<String>>, class: &ClassFile) -> Shape {
    let annotations = class.annotations().unwrap_or_default();
    let jackson = |name: &str| annotations.iter().find(|a| is_jackson(a) && a.simple_name() == name);
    let mut header: Vec<String> = Vec::new();
    let mut members: Vec<Member> = Vec::new();
    let mut problems: Vec<Member> = Vec::new();
    let mut next: Vec<String> = Vec::new();
    let is_abstract = class.is_interface() || class.is_abstract();
    header.push(
        if class.is_record() {
            "record"
        } else if class.is_enum() {
            "enum"
        } else if class.is_interface() {
            "interface"
        } else if class.is_abstract() {
            "abstract class"
        } else {
            "class"
        }
        .to_string(),
    );

    // Where the type is a storage shape too.
    if let Some(mapping) = annotations.iter().find_map(persistence) {
        problems.push(problem(format!("a persistence type ({mapping}) is on the wire: the storage shape is the API shape, and a column renamed for the database renames a field for every client")));
    }

    // Polymorphism: the type ids, from the nearest @JsonTypeInfo.
    let info = type_info(cp, local, class);
    let declares_info = jackson("JsonTypeInfo").is_some();
    if let Some((info, base)) = &info {
        if declares_info {
            if let Some(text) = info.describe() {
                header.push(text);
            }
            if matches!(info.use_.as_str(), "CLASS" | "MINIMAL_CLASS") {
                problems.push(problem("Java class names are the type ids: renaming or moving a subtype changes the wire format, and a reader instantiates whatever class the sender names".to_string()));
            }
            let (registered, listed) = registered_subtypes(class);
            let mut subtypes: Vec<(Option<String>, String)> = listed.clone();
            for permitted in class.permitted_subclasses().unwrap_or_default() {
                if !subtypes.iter().any(|(_, c)| *c == permitted) {
                    if registered {
                        problems.push(problem(format!("{} is a permitted subtype that @JsonSubTypes does not list: it is written under the type id \"{}\", which a reader of {} rejects", simple_name_of(&permitted), default_type_id(&permitted), simple_name_of(&class.name))));
                    }
                    subtypes.push((None, permitted));
                }
            }
            if !matches!(info.use_.as_str(), "DEDUCTION" | "NONE") {
                for (name, subtype) in &subtypes {
                    let id = match info.use_.as_str() {
                        "CLASS" => subtype.replace('/', "."),
                        "MINIMAL_CLASS" => format!(".{}", simple_name_of(subtype)),
                        _ => name.clone().or_else(|| local_class(cp, local, subtype).and_then(|c| type_name_of(&c))).unwrap_or_else(|| default_type_id(subtype)),
                    };
                    members.push(member(format!("subtype \"{id}\" = {}", default_type_id(subtype)), Vec::new(), 0, None));
                }
            } else {
                for (_, subtype) in &subtypes {
                    members.push(member(format!("subtype {}", default_type_id(subtype)), Vec::new(), 0, None));
                }
            }
            next.extend(subtypes.into_iter().map(|(_, c)| c));
        } else if !is_abstract && !class.is_enum() {
            // A concrete subtype: its type id, as the base's registration names it.
            let (registered, listed) = registered_subtypes(base);
            let listed_name: Option<String> = listed.iter().find(|(_, c)| *c == class.name).and_then(|(n, _)| n.clone());
            let in_list = listed.iter().any(|(_, c)| *c == class.name);
            match info.use_.as_str() {
                "NAME" | "SIMPLE_NAME" => {
                    let own_name = type_name_of(class);
                    let id = listed_name.clone().or(own_name.clone()).unwrap_or_else(|| default_type_id(&class.name));
                    // A permitted subtype that is not listed is reported on the base, where the fix goes.
                    let permitted = base.permitted_subclasses().unwrap_or_default().contains(&class.name);
                    if !in_list && !permitted {
                        problems.push(problem(format!("not registered with {}: it is written under the type id \"{id}\", which a reader of {} does not know", simple_name_of(&info.base), simple_name_of(&info.base))));
                    } else if listed_name.is_none() && own_name.is_none() && (in_list || !registered) {
                        problems.push(problem(format!("the type id \"{id}\" is the class name: renaming or moving the class changes the wire format")));
                    }
                    members.push(type_id_member(info, &id));
                }
                "CLASS" => members.push(type_id_member(info, &class.name.replace('/', "."))),
                "MINIMAL_CLASS" => members.push(type_id_member(info, &format!(".{}", simple_name_of(&class.name)))),
                _ => {}
            }
            next.push(info.base.clone());
        }
    } else if is_abstract && !class.is_enum() {
        problems.push(problem(format!("no @JsonTypeInfo: a {} is written as the properties of its runtime class, with no type id to read it back by", simple_name_of(&class.name))));
    }

    // Enum constants.
    if class.is_enum() {
        if let Some(value) = class.methods.iter().find(|m| m.annotations(&class.pool).unwrap_or_default().iter().any(|a| is_jackson(a) && a.simple_name() == "JsonValue")) {
            header.push(format!("written as {} by {}()", return_type_name(class, value), value.name));
        }
        for field in class.fields.iter().filter(|f| f.access & flags::ENUM != 0) {
            let annotations = field.annotations(&class.pool).unwrap_or_default();
            let renamed = annotations.iter().find(|a| is_jackson(a) && a.simple_name() == "JsonProperty").and_then(|a| a.strings("value").into_iter().next()).filter(|n| !n.is_empty());
            let line = match renamed {
                Some(name) => format!("{} as \"{name}\"", field.name),
                None => field.name.clone(),
            };
            let details = annotations.iter().filter(|a| is_jackson(a) && a.simple_name() != "JsonProperty").map(Annotation::render).collect();
            members.push(member(line, details, 0, None));
        }
        let mut all = problems;
        all.extend(members);
        return Shape { header, members: all, next };
    }

    // Properties.
    let strategy = jackson("JsonNaming").and_then(|a| a.classes("value").into_iter().next()).map(|c| simple_name_of(&c));
    if let Some(s) = &strategy {
        header.push(format!("{} names", separated(s.trim_end_matches("Strategy"), '_')));
    }
    let class_include = jackson("JsonInclude").cloned();
    let ignored_names: Vec<String> = jackson("JsonIgnoreProperties").map(|a| a.strings("value")).unwrap_or_default();
    if jackson("JsonIgnoreProperties").is_some_and(|a| matches!(a.element("ignoreUnknown"), Some(crate::classfile::ElementValue::Boolean(true)))) {
        header.push("ignores unknown properties".to_string());
    }
    for a in annotations.iter().filter(|a| is_jackson(a) && !matches!(a.simple_name().as_str(), "JsonTypeInfo" | "JsonSubTypes" | "JsonTypeName" | "JsonIgnoreProperties" | "JsonInclude" | "JsonNaming" | "JsonPropertyOrder" | "JsonCreator")) {
        header.push(a.render());
    }
    let mut props: Vec<Prop> = properties(cp, local, class).into_iter().filter(|p| (p.creates || p.explicit.is_some()) && !p.ignored).collect();
    if let Some(order) = jackson("JsonPropertyOrder") {
        let first = order.strings("value");
        let position = |p: &Prop| first.iter().position(|n| p.explicit.as_deref() == Some(n) || p.implicit == *n).unwrap_or(first.len());
        props.sort_by_key(position);
    }
    let mut lines: Vec<Member> = Vec::new();
    let mut names: BTreeSet<String> = BTreeSet::new();
    for p in &props {
        let name = match &p.explicit {
            Some(n) => n.clone(),
            None => strategy.as_deref().map(|s| renamed(s, &p.implicit)).unwrap_or_else(|| p.implicit.clone()),
        };
        if ignored_names.contains(&name) {
            continue;
        }
        if !names.insert(name.clone()) {
            problems.push(problem(format!("two properties are named \"{name}\"")));
        }
        let (ty, mut optional) = unwrap_optional(&p.rendered_type());
        if let Some(omit) = p.include.as_ref().or(class_include.as_ref()).and_then(omits) {
            optional |= omit || !is_primitive(&ty);
        }
        let constraints = if p.constraints.is_empty() { String::new() } else { format!("{} ", render_all(&p.constraints)) };
        let line = format!("{name}: {constraints}{ty}{}", if optional { "?" } else { "" });
        let mut details: Vec<String> = p.details.iter().map(Annotation::render).collect();
        let mut prop_problems = p.constraint_problems(cp);
        // A nested type's constraints run only when a @Valid leads into it.
        if !p.cascades() {
            let unreached: Vec<String> = p.referenced().into_iter().filter(|c| validation::constrained(cp, local, c)).map(|c| simple_name_of(&c)).collect();
            if !unreached.is_empty() {
                prop_problems.push(format!("constraints on {} are not checked: no @Valid on {name}", unreached.join(", ")));
            }
        }
        let count = prop_problems.len();
        details.extend(prop_problems.into_iter().map(|t| format!("! {t}")));
        lines.push(member(line, details, count, p.source_line));
    }
    for method in &class.methods {
        let annotations = method.annotations(&class.pool).unwrap_or_default();
        if annotations.iter().any(|a| is_jackson(a) && a.simple_name() == "JsonAnyGetter") {
            lines.push(member(format!("*: {}", return_type_name(class, method)), Vec::new(), 0, method.first_line()));
        } else if annotations.iter().any(|a| is_jackson(a) && a.simple_name() == "JsonAnySetter") && !lines.iter().any(|l| l.line.starts_with("*: ")) {
            lines.push(member(format!("*: {}", parameter_type_names(class, method).last().cloned().unwrap_or_default()), Vec::new(), 0, method.first_line()));
        }
    }
    if lines.is_empty() && !is_abstract && !declares_info {
        problems.push(problem("no properties: it is written as {}".to_string()));
    }
    let mut all = problems;
    all.extend(members);
    all.extend(lines);
    Shape { header, members: all, next }
}

fn type_id_member(info: &TypeInfo, id: &str) -> Member {
    match info.include.as_str() {
        "WRAPPER_OBJECT" => member(format!("wrapped in an object under \"{id}\""), Vec::new(), 0, None),
        "WRAPPER_ARRAY" => member(format!("wrapped in an array after \"{id}\""), Vec::new(), 0, None),
        _ => member(format!("{} = \"{id}\"", info.property), Vec::new(), 0, None),
    }
}

/// The classes a type's own members name, as internal names: record component and field types, getter return
/// types, setter parameter types.
fn referenced(class: &ClassFile) -> Vec<String> {
    let mut out = Vec::new();
    for field in &class.fields {
        if field.is_static() {
            continue;
        }
        out.extend(class_refs(&field.generic_signature(&class.pool).unwrap_or_else(|| field.descriptor.clone())));
    }
    for method in &class.methods {
        if method.is_static() || method.is_constructor() || method.is_class_initializer() || method.is_synthetic() {
            continue;
        }
        let (params, ret) = method_refs(class, method);
        if method.descriptor.starts_with("()") {
            out.extend(ret);
        } else if params.len() == 1 && method.descriptor.ends_with(")V") {
            out.extend(params.into_iter().flatten());
        }
    }
    out
}

/// The wire types reachable from the roots (internal names): one block per type, keyed by binary name with dots.
pub fn analyse(cp: &ClassPath, local: Option<&BTreeSet<String>>, roots: &[String]) -> Result<BTreeMap<String, Bean>, Error> {
    let mut out = BTreeMap::new();
    let mut queue: VecDeque<String> = roots.iter().cloned().collect();
    let mut seen: BTreeSet<String> = BTreeSet::new();
    while let Some(name) = queue.pop_front() {
        if !seen.insert(name.clone()) {
            continue;
        }
        let Some(class) = local_class(cp, local, &name) else { continue };
        if class.access & flags::ANNOTATION != 0 || class.access & flags::SYNTHETIC != 0 {
            continue;
        }
        let shape = shape(cp, local, &class);
        queue.extend(shape.next);
        // The member types, from the class's own signatures; the superclass is followed for its members' types.
        queue.extend(referenced(&class));
        if let Some(sc) = class.super_class.as_deref().filter(|s| !s.starts_with("java/")) {
            queue.push_back(sc.to_string());
        }
        out.insert(name.replace('/', "."), Bean { annotations: shape.header.join(", "), members: shape.members });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_follow_jackson() {
        assert_eq!(decapitalize("URL"), "URL");
        assert_eq!(decapitalize("CustomerName"), "customerName");
        assert_eq!(separated("customerName", '_'), "customer_name");
        assert_eq!(separated("URL", '_'), "url");
        assert_eq!(renamed("KebabCaseStrategy", "orderId"), "order-id");
        assert_eq!(renamed("UpperCamelCaseStrategy", "orderId"), "OrderId");
        assert_eq!(default_type_id("net/x/PaymentEvent$PaymentCaptured"), "PaymentEvent$PaymentCaptured");
        assert_eq!(unwrap_optional("Optional<String>"), ("String".to_string(), true));
    }

    #[test]
    fn class_refs_skip_type_variables_and_inner_names() {
        assert_eq!(class_refs("Ljava/util/List<Lnet/x/Order;>;"), vec!["java/util/List", "net/x/Order"]);
        assert_eq!(class_refs("(Lnet/x/Outer<TT;>.Lower;I)Lnet/x/Result;"), vec!["net/x/Outer", "net/x/Result"]);
        assert_eq!(class_refs("Ljava/util/Map<Ljava/lang/String;+Lnet/x/Seat;>;"), vec!["java/util/Map", "java/lang/String", "net/x/Seat"]);
        assert!(class_refs("I").is_empty());
    }
}
