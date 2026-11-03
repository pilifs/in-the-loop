//! Jakarta Validation as the boundary contract checks it: whether each constraint on a wire type can run on the
//! type it is on, whether a nested type's constraints are reached by a `@Valid`, and which constraints a handler's
//! `@Valid` or `@Validated(groups)` leaves out.
//!
//! The facts are the specification's (Jakarta Validation 3.1, section 8) and Hibernate Validator's, which is what
//! Spring Boot ships: a built-in constraint has validators for a fixed set of types, and a constraint on any other
//! type is accepted by the compiler and fails at the first validation with `UnexpectedTypeException`
//! (`HV000030: No validator could be found for constraint ... validating type ...`). Validation does not step into
//! a property's type unless `@Valid` is on the property or on the type argument (`List<@Valid Item>`), and a
//! constraint runs only in its groups (`Default` when none are named): `@Valid` on a handler parameter validates
//! the `Default` group, `@Validated(G.class)` validates `G` and the groups it extends.

use std::collections::BTreeSet;

use crate::classfile::signature::{self, Sig};
use crate::classfile::{simple_name_of, Annotation};
use crate::classpath::ClassPath;
use crate::wire;

const CONSTRAINT_PACKAGES: &[&str] = &["jakarta/validation/constraints/", "javax/validation/constraints/", "org/hibernate/validator/constraints/"];
const VALID: &[&str] = &["jakarta/validation/Valid", "javax/validation/Valid"];
pub const DEFAULT_GROUP: &str = "jakarta/validation/groups/Default";
const DEFAULT_GROUPS: &[&str] = &[DEFAULT_GROUP, "javax/validation/groups/Default"];

/// A built-in constraint: one of the specification's or Hibernate Validator's.
pub fn is_constraint(a: &Annotation) -> bool {
    CONSTRAINT_PACKAGES.iter().any(|p| a.type_name.starts_with(p))
}

/// `@Valid`: validation steps into the annotated value.
pub fn is_valid(a: &Annotation) -> bool {
    VALID.contains(&a.type_name.as_str())
}

/// The families of types the built-in constraints have validators for.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum Family {
    Text,
    Number,
    Bool,
    Collection,
    Map,
    Array,
    Temporal,
    Duration,
    Money,
}

const FAMILIES: &[(Family, &[&str])] = &[
    (Family::Text, &["java/lang/CharSequence", "java/lang/String", "java/lang/StringBuilder", "java/lang/StringBuffer", "java/nio/CharBuffer"]),
    (
        Family::Number,
        &[
            "java/lang/Number",
            "java/lang/Integer",
            "java/lang/Long",
            "java/lang/Short",
            "java/lang/Byte",
            "java/lang/Double",
            "java/lang/Float",
            "java/math/BigDecimal",
            "java/math/BigInteger",
            "java/util/concurrent/atomic/AtomicInteger",
            "java/util/concurrent/atomic/AtomicLong",
        ],
    ),
    (Family::Bool, &["java/lang/Boolean"]),
    (
        Family::Collection,
        &[
            "java/util/Collection",
            "java/util/List",
            "java/util/Set",
            "java/util/Queue",
            "java/util/Deque",
            "java/util/SortedSet",
            "java/util/NavigableSet",
            "java/util/SequencedCollection",
            "java/util/SequencedSet",
            "java/util/AbstractCollection",
            "java/util/AbstractList",
            "java/util/AbstractSet",
            "java/util/ArrayList",
            "java/util/LinkedList",
            "java/util/HashSet",
            "java/util/LinkedHashSet",
            "java/util/TreeSet",
            "java/util/ArrayDeque",
            "java/util/PriorityQueue",
            "java/util/Vector",
            "java/util/Stack",
            "java/util/EnumSet",
            "java/util/concurrent/CopyOnWriteArrayList",
        ],
    ),
    (
        Family::Map,
        &[
            "java/util/Map",
            "java/util/SortedMap",
            "java/util/NavigableMap",
            "java/util/SequencedMap",
            "java/util/AbstractMap",
            "java/util/HashMap",
            "java/util/LinkedHashMap",
            "java/util/TreeMap",
            "java/util/EnumMap",
            "java/util/Hashtable",
            "java/util/Properties",
            "java/util/concurrent/ConcurrentMap",
            "java/util/concurrent/ConcurrentHashMap",
        ],
    ),
    (
        Family::Temporal,
        &[
            "java/util/Date",
            "java/sql/Date",
            "java/sql/Time",
            "java/sql/Timestamp",
            "java/util/Calendar",
            "java/util/GregorianCalendar",
            "java/time/Instant",
            "java/time/LocalDate",
            "java/time/LocalDateTime",
            "java/time/LocalTime",
            "java/time/MonthDay",
            "java/time/OffsetDateTime",
            "java/time/OffsetTime",
            "java/time/Year",
            "java/time/YearMonth",
            "java/time/ZonedDateTime",
            "java/time/chrono/HijrahDate",
            "java/time/chrono/JapaneseDate",
            "java/time/chrono/MinguoDate",
            "java/time/chrono/ThaiBuddhistDate",
        ],
    ),
    (Family::Duration, &["java/time/Duration"]),
    (Family::Money, &["javax/money/MonetaryAmount"]),
];

/// The families a built-in constraint has validators for; `None` for a constraint this table does not know, and
/// an empty list for one that takes any type.
fn accepted(simple: &str) -> Option<&'static [Family]> {
    Some(match simple {
        "Null" | "NotNull" => &[],
        "AssertTrue" | "AssertFalse" => &[Family::Bool],
        "Min" | "Max" | "DecimalMin" | "DecimalMax" | "Digits" | "Positive" | "PositiveOrZero" | "Negative" | "NegativeOrZero" => &[Family::Number, Family::Text, Family::Money],
        "Range" => &[Family::Number, Family::Text],
        "Size" | "NotEmpty" => &[Family::Text, Family::Collection, Family::Map, Family::Array],
        "NotBlank" | "Pattern" | "Email" | "Length" | "URL" | "UUID" | "CreditCardNumber" | "EAN" | "ISBN" | "LuhnCheck" | "Mod10Check" | "Mod11Check" | "CodePointLength" | "Normalized" | "NIP" | "PESEL" | "REGON" | "INN" | "CNPJ" | "CPF" | "TituloEleitoral" | "NIE" | "DNI" | "NIF" => &[Family::Text],
        "Past" | "PastOrPresent" | "Future" | "FutureOrPresent" => &[Family::Temporal],
        "DurationMin" | "DurationMax" => &[Family::Duration],
        "UniqueElements" => &[Family::Collection],
        "Currency" => &[Family::Money],
        _ => return None,
    })
}

/// The families of a class, from the table over the class and its supertypes. `None` when a supertype could not
/// be found, so the answer is not known.
fn families(cp: &ClassPath, name: &str) -> Option<BTreeSet<Family>> {
    let mut out = BTreeSet::new();
    let mut seen = BTreeSet::new();
    let mut complete = true;
    let mut work = vec![name.to_string()];
    while let Some(current) = work.pop() {
        if !seen.insert(current.clone()) {
            continue;
        }
        for (family, names) in FAMILIES {
            if names.contains(&current.as_str()) {
                out.insert(*family);
            }
        }
        if current == "java/lang/Object" {
            continue;
        }
        if !cp.exists(&current) {
            complete = false;
            continue;
        }
        if let Some(s) = cp.superclass(&current) {
            work.push(s);
        }
        work.extend(cp.interfaces(&current));
    }
    (!out.is_empty() || complete).then_some(out)
}

/// `Optional<T>` and the primitive optionals are validated as their value, as the default value extractors unwrap
/// them.
fn unwrapped(ty: &Sig) -> Option<Sig> {
    match ty {
        Sig::Class { name, args } if name == "java/util/Optional" => args.first().cloned(),
        Sig::Class { name, .. } if name == "java/util/OptionalInt" => Some(Sig::Primitive('I')),
        Sig::Class { name, .. } if name == "java/util/OptionalLong" => Some(Sig::Primitive('J')),
        Sig::Class { name, .. } if name == "java/util/OptionalDouble" => Some(Sig::Primitive('D')),
        _ => None,
    }
}

/// Whether the constraint has a validator for the type: `None` when the constraint or the type is not known.
fn supports(cp: &ClassPath, constraint: &Annotation, ty: &Sig) -> Option<bool> {
    let accepted = accepted(&constraint.simple_name())?;
    if accepted.is_empty() {
        return Some(true);
    }
    let ty = unwrapped(ty).unwrap_or_else(|| ty.clone());
    let families: BTreeSet<Family> = match &ty {
        Sig::Primitive('Z') => [Family::Bool].into(),
        Sig::Primitive('B' | 'S' | 'I' | 'J' | 'F' | 'D') => [Family::Number].into(),
        Sig::Primitive(_) => BTreeSet::new(),
        Sig::Array(_) => [Family::Array].into(),
        Sig::Class { name, .. } => families(cp, name)?,
        Sig::Variable(_) | Sig::Wildcard(_) => return None,
    };
    Some(accepted.iter().any(|f| families.contains(f)))
}

/// A type as a reader of the source sees it: simple names, type arguments, `[]`.
pub fn render(ty: &Sig) -> String {
    match ty {
        Sig::Class { name, args } if args.is_empty() => simple_name_of(name),
        Sig::Class { name, args } => format!("{}<{}>", simple_name_of(name), args.iter().map(render).collect::<Vec<_>>().join(", ")),
        Sig::Array(elem) => format!("{}[]", render(elem)),
        Sig::Primitive(c) => crate::classfile::Type::parse(&c.to_string()).map(|t| t.java_name()).unwrap_or_else(|_| c.to_string()),
        Sig::Variable(name) => name.clone(),
        Sig::Wildcard(None) => "?".to_string(),
        Sig::Wildcard(Some((true, bound))) => format!("? extends {}", render(bound)),
        Sig::Wildcard(Some((false, bound))) => format!("? super {}", render(bound)),
    }
}

/// What is wrong with the constraint on the type, if anything: no validator for the type, or a null check on a
/// primitive.
pub fn problem(cp: &ClassPath, constraint: &Annotation, ty: &Sig) -> Option<String> {
    let simple = constraint.simple_name();
    let rendered = render(ty);
    if let Sig::Primitive(_) = ty {
        match simple.as_str() {
            "NotNull" => return Some(format!("@NotNull on {rendered} can never fail: a primitive is never null")),
            "Null" => return Some(format!("@Null on {rendered} always fails: a primitive is never null")),
            _ => {}
        }
    }
    if supports(cp, constraint, ty) == Some(false) {
        return Some(format!("@{simple} has no validator for {rendered}: the first validation throws UnexpectedTypeException"));
    }
    None
}

/// The groups a constraint runs in: its `groups` element, or `Default`.
fn groups_of(constraint: &Annotation) -> Vec<String> {
    let groups = constraint.classes("groups");
    if groups.is_empty() {
        vec![DEFAULT_GROUP.to_string()]
    } else {
        groups
    }
}

fn is_default(group: &str) -> bool {
    DEFAULT_GROUPS.contains(&group)
}

/// Whether a constraint in `groups` runs when `validated` are the groups asked for: a group asked for runs the
/// constraints of the groups it extends.
fn runs(cp: &ClassPath, groups: &[String], validated: &[String]) -> bool {
    validated.iter().any(|v| groups.iter().any(|g| v == g || (is_default(v) && is_default(g)) || cp.is_subtype(v, g)))
}

/// The constraint without its `groups`, for a line that is about the group.
fn without_groups(constraint: &Annotation) -> String {
    let mut a = constraint.clone();
    a.elements.retain(|(n, _)| n != "groups");
    a.render()
}

/// The constrained wire types among the classes, with the walk's memory so that a cycle ends.
fn constrained_in(cp: &ClassPath, local: Option<&BTreeSet<String>>, class: &str, seen: &mut BTreeSet<String>) -> bool {
    if !seen.insert(class.to_string()) {
        return false;
    }
    let Some(class) = wire::local_class(cp, local, class) else { return false };
    for p in wire::properties(cp, local, &class) {
        if p.constraints.iter().any(is_constraint) || p.type_constraints.iter().any(|t| is_constraint(&t.annotation)) {
            return true;
        }
        if p.cascades() && p.referenced().iter().any(|c| constrained_in(cp, local, c, seen)) {
            return true;
        }
    }
    false
}

/// Whether the class carries constraints, on its own properties or on those `@Valid` steps into.
pub fn constrained(cp: &ClassPath, local: Option<&BTreeSet<String>>, class: &str) -> bool {
    constrained_in(cp, local, class, &mut BTreeSet::new())
}

/// The constraints of the class, and of the types `@Valid` steps into, that validating `groups` (`None` for
/// `Default`) does not run: `@NotBlank(groups = OnCreate.class) on Booking.code`, without the groups when the groups
/// asked for are not the default.
pub fn unchecked(cp: &ClassPath, local: Option<&BTreeSet<String>>, class: &str, groups: Option<&[String]>) -> Vec<String> {
    let validated: Vec<String> = groups.map(|g| g.to_vec()).unwrap_or_else(|| vec![DEFAULT_GROUP.to_string()]);
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    let mut work = vec![class.to_string()];
    while let Some(name) = work.pop() {
        if !seen.insert(name.clone()) {
            continue;
        }
        let Some(class) = wire::local_class(cp, local, &name) else { continue };
        let simple = simple_name_of(&class.name);
        for p in wire::properties(cp, local, &class) {
            let all: Vec<&Annotation> = p.constraints.iter().chain(p.type_constraints.iter().map(|t| &t.annotation)).filter(|a| is_constraint(a)).collect();
            for c in all {
                if !runs(cp, &groups_of(c), &validated) {
                    let shown = if groups.is_some() { without_groups(c) } else { c.render() };
                    out.push(format!("{shown} on {simple}.{}", p.implicit));
                }
            }
            if p.cascades() {
                work.extend(p.referenced());
            }
        }
    }
    out
}

/// The `groups` of a `@Validated`, when it names any.
pub fn validated_groups(a: &Annotation) -> Option<Vec<String>> {
    let groups = a.classes("value");
    (!groups.is_empty()).then_some(groups)
}

/// A type with the annotations of a type path written into it: `List<@NotBlank String>`.
pub fn annotate(rendered: &str, path: &[(u8, u8)], text: &str) -> String {
    let Some(&(kind, index)) = path.first() else { return format!("{text} {rendered}") };
    match kind {
        3 => {
            let Some(open) = rendered.find('<') else { return rendered.to_string() };
            let Some(inner) = rendered[open + 1..].strip_suffix('>') else { return rendered.to_string() };
            let mut args: Vec<String> = Vec::new();
            let mut depth = 0;
            let mut start = 0;
            for (i, c) in inner.char_indices() {
                match c {
                    '<' => depth += 1,
                    '>' => depth -= 1,
                    ',' if depth == 0 => {
                        args.push(inner[start..i].trim().to_string());
                        start = i + 1;
                    }
                    _ => {}
                }
            }
            args.push(inner[start..].trim().to_string());
            if let Some(arg) = args.get_mut(index as usize) {
                *arg = annotate(arg, &path[1..], text);
            }
            format!("{}<{}>", &rendered[..open], args.join(", "))
        }
        0 => match rendered.strip_suffix("[]") {
            Some(elem) => format!("{}[]", annotate(elem, &path[1..], text)),
            None => rendered.to_string(),
        },
        2 => match rendered.strip_prefix("? extends ").or_else(|| rendered.strip_prefix("? super ")) {
            Some(bound) => format!("{}{}", &rendered[..rendered.len() - bound.len()], annotate(bound, &path[1..], text)),
            None => rendered.to_string(),
        },
        _ => rendered.to_string(),
    }
}

impl signature::Sig {
    /// The classes the type names, as internal names, outermost first.
    pub fn classes(&self) -> Vec<String> {
        let mut out = Vec::new();
        self.collect(&mut out);
        out
    }

    fn collect(&self, out: &mut Vec<String>) {
        match self {
            Sig::Class { name, args } => {
                out.push(name.clone());
                args.iter().for_each(|a| a.collect(out));
            }
            Sig::Array(elem) => elem.collect(out),
            Sig::Wildcard(Some((_, bound))) => bound.collect(out),
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn constraint(name: &str) -> Annotation {
        Annotation { type_name: format!("jakarta/validation/constraints/{name}"), elements: Vec::new() }
    }

    #[test]
    fn constraints_need_a_validator_for_the_type() {
        let cp = ClassPath::new();
        let string = signature::parse_type("Ljava/lang/String;").unwrap();
        let int = signature::parse_type("I").unwrap();
        let list = signature::parse_type("Ljava/util/List<Ljava/lang/String;>;").unwrap();
        let optional = signature::parse_type("Ljava/util/Optional<Ljava/lang/Integer;>;").unwrap();
        assert_eq!(supports(&cp, &constraint("NotBlank"), &string), Some(true));
        assert_eq!(supports(&cp, &constraint("NotBlank"), &list), Some(false));
        assert_eq!(supports(&cp, &constraint("Size"), &int), Some(false));
        assert_eq!(supports(&cp, &constraint("Size"), &list), Some(true));
        assert_eq!(supports(&cp, &constraint("Min"), &optional), Some(true));
        assert_eq!(supports(&cp, &constraint("Min"), &string), Some(true), "Hibernate Validator reads the number in a string");
        assert_eq!(supports(&cp, &constraint("NotNull"), &int), Some(true));
        assert_eq!(supports(&cp, &constraint("Past"), &signature::parse_type("Ljava/time/Instant;").unwrap()), Some(true));
        assert_eq!(supports(&cp, &constraint("Past"), &string), Some(false));
        assert_eq!(supports(&cp, &constraint("Custom"), &string), None);
        assert_eq!(supports(&cp, &constraint("Size"), &signature::parse_type("Lnet/example/Unknown;").unwrap()), None, "a type that cannot be found is not judged");
        assert_eq!(problem(&cp, &constraint("NotNull"), &int).as_deref(), Some("@NotNull on int can never fail: a primitive is never null"));
        assert_eq!(problem(&cp, &constraint("Null"), &int).as_deref(), Some("@Null on int always fails: a primitive is never null"));
        assert_eq!(problem(&cp, &constraint("NotNull"), &string), None);
        assert_eq!(problem(&cp, &constraint("Size"), &int).as_deref(), Some("@Size has no validator for int: the first validation throws UnexpectedTypeException"));
        assert_eq!(problem(&cp, &constraint("Size"), &list), None);
    }

    #[test]
    fn type_annotations_are_written_into_the_type() {
        assert_eq!(annotate("List<String>", &[(3, 0)], "@NotBlank"), "List<@NotBlank String>");
        assert_eq!(annotate("Map<String, List<Item>>", &[(3, 1), (3, 0)], "@Valid"), "Map<String, List<@Valid Item>>");
        assert_eq!(annotate("String[]", &[(0, 0)], "@NotBlank"), "@NotBlank String[]");
        assert_eq!(annotate("List<? extends Number>", &[(3, 0), (2, 0)], "@Min(1)"), "List<? extends @Min(1) Number>");
        assert_eq!(annotate("String", &[], "@NotBlank"), "@NotBlank String");
    }

    #[test]
    fn groups_decide_what_runs() {
        let cp = ClassPath::new();
        let default = vec![DEFAULT_GROUP.to_string()];
        let create = vec!["net/example/OnCreate".to_string()];
        assert!(runs(&cp, &default, &default));
        assert!(!runs(&cp, &create, &default));
        assert!(runs(&cp, &create, &create));
        assert!(!runs(&cp, &default, &create));
    }
}
