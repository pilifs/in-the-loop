//! The objects stream's module (`llm-dlc/loops/application-core-objects.md`): the common construction plan
//! ([`ConstructionPlan`]) of receivers, parameters, bounded arrays and short setup sequences, fed through
//! `equivalence`, `prove` and `compare`. Registered by Phase 0 of `llm-dlc/loops/application-core.md`, so that the
//! stream starts without editing a shared file. Until the stream builds a part, its entry point returns
//! [`Unsupported`] naming it, and every call site refuses the claim that needs it: no plan falls back to the
//! constructor domain the checks make today.

use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::spec::plans::{ConstructionPlan, Maker, PlanValue};
use crate::spec::{Part, Unsupported};

fn unbuilt(what: &str) -> Unsupported {
    Unsupported::new(Part::Objects, format!("{what}: the objects stream builds it (llm-dlc/loops/application-core-objects.md)"))
}

/// The two versions' plans of a regression check, as `--plan FILE` gives them and a [`crate::spec::Construction::Planned`]
/// domain holds them.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Plans {
    pub before: ConstructionPlan,
    pub after: ConstructionPlan,
}

/// Checks a claim's plans for the two versions: their shape ([`ConstructionPlan::shape_problem`]), then whether a
/// check can make its inputs by them. Called by the domain gate (`spec::heap`) for a planned domain.
///
/// What a check makes today: roots that are primitive leaves or objects, each object made once by the constructor
/// its node names (an explicit choice among several), from primitive leaves named by their path from the root
/// (`this.capacity`, `q.amount.cents`) and objects made so in turn; and a setup sequence of at most
/// [`MAX_SETUP_CALLS`] calls on the receiver, of primitive leaves (`setup.0.n`), the same in both versions. A root
/// may be null, or one of the objects of other roots, or the same node as another root, one object ([`choices`],
/// the same in both versions). A root may also be an adapted list (`List<E>` of the values stream's
/// `values::ListAdapter`, V2), named as the root, never null, of objects of an application class made by its
/// constructor, as the check makes a list parameter's elements: its domain resolved under this tool's list model
/// (`values::resolve`, which refuses a claim stated under another model, JDK or a stronger level), and the same in
/// both versions. What it doesn't make yet is refused by its stream's name, before any check: such a choice or
/// sharing inside a nested object, a null array, a factory, a dependency (the objects stream's), an adapted String
/// root, and an adapted value inside a node (the values stream's adapter).
pub fn check_plans(before: &ConstructionPlan, after: &ConstructionPlan) -> Result<(), Unsupported> {
    for (version, plan) in [("previous", before), ("new", after)] {
        if let Some(problem) = plan.shape_problem() {
            return Err(Unsupported::new(Part::Objects, format!("the {version} version's construction plan: {problem}")));
        }
    }
    for (version, plan) in [("previous", before), ("new", after)] {
        let mut used = Vec::new();
        for node in &plan.nodes {
            if let Maker::Factory { method } = &node.maker {
                return Err(unbuilt(&format!("the {version} version's plan makes node {} by the factory {method}, and a factory maker", node.id)));
            }
        }
        // The objects inside others first: each made once, with no choice of its own (the recipe makes an inner object
        // as its constructor's argument, and the harness chooses only among the roots).
        for n in &plan.nodes {
            for value in &n.args {
                supported(version, &format!("node {}", n.id), value, &mut used)?;
            }
        }
        let inner = used.clone();
        for r in &plan.roots {
            supported_root(version, plan, r, &inner)?;
        }
        // A leaf or an array is named by its path: one given at two places would be one value at two paths, which
        // the flat parameters can't be (an array shared by two objects is the shared arrays' case).
        let mut paths: Vec<&str> = Vec::new();
        for value in plan.roots.iter().map(|r| &r.value).chain(plan.nodes.iter().flat_map(|n| n.args.iter())).chain(plan.setup.iter().flat_map(|c| c.args.iter())) {
            if let PlanValue::Leaf { path, .. } | PlanValue::Array { path, .. } = value {
                if paths.contains(&path.as_str()) {
                    return Err(unbuilt(&format!("the {version} version's plan gives {path} twice, one value at two paths, and a plan's shared values")));
                }
                paths.push(path);
            }
        }
        if plan.setup.len() > MAX_SETUP_CALLS {
            return Err(Unsupported::new(Part::Objects, format!("the {version} version's setup sequence has {} calls: a selected sequence of at most {MAX_SETUP_CALLS} is supported, and a longer history is outside this wave", plan.setup.len())));
        }
        for call in &plan.setup {
            for arg in &call.args {
                match arg {
                    PlanValue::Leaf { .. } => supported(version, &format!("the setup call {}", call.method), arg, &mut used)?,
                    _ => return Err(unbuilt(&format!("the {version} version's setup call {} takes {}, and a setup argument other than a primitive leaf", call.method, value_name(arg)))),
                }
            }
        }
        if plan.roots.iter().any(|r| r.name == "this" && matches!(r.value, PlanValue::Node { nullable: true, .. })) {
            return Err(Unsupported::new(Part::Objects, format!("the {version} version's plan lets the receiver this be null: the receiver of an instance method is never null")));
        }
        if !plan.setup.is_empty() && !plan.roots.iter().any(|r| r.name == "this") {
            return Err(Unsupported::new(Part::Objects, format!("the {version} version's plan has a setup sequence and no receiver: setup calls are made on this")));
        }
    }
    let names = |p: &ConstructionPlan| p.roots.iter().map(|r| r.name.clone()).collect::<Vec<_>>();
    if names(before) != names(after) {
        return Err(Unsupported::new(Part::Objects, format!("the plans' roots differ: {} before, {} now; both versions are given the same inputs", names(before).join(", "), names(after).join(", "))));
    }
    // An adapted list root is one value both versions are given: the same domain in each.
    for r in &after.roots {
        let PlanValue::Adapted { domain, .. } = &r.value else { continue };
        let previous = before.roots.iter().find(|b| b.name == r.name).map(|b| &b.value);
        if !matches!(previous, Some(PlanValue::Adapted { domain: d, .. }) if d == domain) {
            return Err(Unsupported::new(Part::Objects, format!("the plans' root {} differs: the new version's is an adapted list, and the previous version's is {}; both versions are given the same list", r.name, previous.map(value_name).map(|n| format!("{n}, another value")).unwrap_or_else(|| "absent".into()))));
        }
    }
    if choices(before) != choices(after) {
        return Err(Unsupported::new(Part::Objects, format!("the plans' choices of null and of one object differ: {} before, {} now; both versions are given the same choices, so that their identity relations start alike", choices(before), choices(after))));
    }
    let steps = |p: &ConstructionPlan| p.setup.iter().map(|c| format!("{}({})", c.method, c.args.iter().map(value_name).collect::<Vec<_>>().join(", "))).collect::<Vec<_>>();
    if steps(before) != steps(after) {
        return Err(Unsupported::new(Part::Objects, format!("the setup sequences differ: {} before, {} now; both versions are given the same setup calls on the same logical inputs", steps(before).join(" then "), steps(after).join(" then "))));
    }
    Ok(())
}

/// The type a plan writes as Java does (`int`, `long[]`, `shop.Money`).
fn java_type(name: &str) -> Option<crate::classfile::Type> {
    use crate::classfile::Type;
    if let Some(element) = name.strip_suffix("[]") {
        return java_type(element).map(|e| Type::Array(Box::new(e)));
    }
    Some(match name {
        "boolean" => Type::Boolean,
        "byte" => Type::Byte,
        "char" => Type::Char,
        "short" => Type::Short,
        "int" => Type::Int,
        "long" => Type::Long,
        "float" => Type::Float,
        "double" => Type::Double,
        "" | "void" => return None,
        class => Type::Object(class.replace('.', "/")),
    })
}

/// A statement's bounds, with what a construction adds: the setup sequence's length (O3), and the array bound where
/// an object's construction takes an array (O1), which the statement's parameters alone don't show.
pub fn stated_bounds(layout: &crate::harness::Layout, bounds: crate::statement::Bounds, max_array_length: u32) -> crate::statement::Bounds {
    let arrays = layout.params.iter().any(|p| matches!(p.ty, crate::classfile::Type::Array(_)));
    crate::statement::Bounds {
        setup_calls: (!layout.setup.is_empty()).then_some(layout.setup.len() as u32),
        max_array_length: if arrays { Some(max_array_length) } else { bounds.max_array_length },
        ..bounds
    }
}

/// The longest setup sequence a plan may have (O3): one or two calls, never a search over histories.
pub const MAX_SETUP_CALLS: usize = 2;

/// A value as a refusal names it: `this.capacity`, `node 2`.
fn value_name(value: &PlanValue) -> String {
    match value {
        PlanValue::Leaf { path, .. } | PlanValue::Array { path, .. } | PlanValue::Adapted { path, .. } | PlanValue::Dependency { path, .. } => path.clone(),
        PlanValue::Node { id, .. } => format!("node {id}"),
    }
}

/// Whether a check makes `value`, at `at` of the `version` plan: `used` are the nodes used so far, each once.
fn supported(version: &str, at: &str, value: &PlanValue, used: &mut Vec<u32>) -> Result<(), Unsupported> {
    match value {
        PlanValue::Leaf { path, ty } => match java_type(ty) {
            Some(t) if t.is_primitive() => Ok(()),
            _ => Err(Unsupported::new(Part::Objects, format!("the {version} version's leaf {path} has type {ty}, and a leaf is a primitive"))),
        },
        PlanValue::Array { path, element, nullable, .. } => {
            if !java_type(element).is_some_and(|e| crate::harness::is_leaf(&crate::classfile::Type::Array(Box::new(e)))) {
                return Err(Unsupported::new(Part::Objects, format!("the {version} version's array {path} has elements of type {element}: an array leaf is of integral or boolean elements")));
            }
            if *nullable {
                return Err(unbuilt(&format!("the {version} version's array {path} may be null, and a plan's null array")));
            }
            Ok(())
        }
        PlanValue::Adapted { path, .. } => Err(Unsupported::new(Part::Values, format!("the {version} version's {at} takes {path}, an adapted value: the values stream builds it (llm-dlc/loops/application-core-values.md)"))),
        PlanValue::Dependency { path, class } => Err(unbuilt(&format!("the {version} version's {at} takes {path}, a dependency of {class} the environment model stands for, and a construction with dependencies"))),
        PlanValue::Node { id, nullable, same_as } => {
            if *nullable || !same_as.is_empty() {
                return Err(unbuilt(&format!("the {version} version's {at} takes node {id}, which may be null or one of several: a choice inside a nested object, where the harness chooses only among the roots, and a plan's nested choices")));
            }
            if used.contains(id) {
                return Err(unbuilt(&format!("the {version} version's {at} takes node {id} again, one object at two paths inside nested objects, and a plan's nested shared nodes")));
            }
            used.push(*id);
            Ok(())
        }
    }
}

/// Whether a check makes the root `r` of the `version` plan: a leaf or an array as [`supported`] says, or a node
/// (O2) that may be null (`nullable`), or one of the objects of earlier roots (`same_as`, by their nodes' ids, each a
/// node of the same class at another root), or a node another root is too (one object, always): never a node that is
/// part of another (`inner`), and a node at two roots has no choice at either.
fn supported_root(version: &str, plan: &ConstructionPlan, r: &crate::spec::plans::Root, inner: &[u32]) -> Result<(), Unsupported> {
    if let PlanValue::Adapted { path, domain } = &r.value {
        return adapted_root(&format!("the {version} version's"), &r.name, path, domain).map(|_| ());
    }
    let PlanValue::Node { id, nullable, same_as } = &r.value else { return supported(version, &r.name, &r.value, &mut Vec::new()) };
    let gap = |what: String| Unsupported::new(Part::Objects, format!("the {version} version's root {}: {what}", r.name));
    if inner.contains(id) {
        return Err(unbuilt(&format!("the {version} version's root {} is node {id}, which is part of another node too: an object shared between a root and a nested object, and a plan's nested shared nodes", r.name)));
    }
    let class = |id: u32| plan.nodes.iter().find(|n| n.id == id).map(|n| n.class.clone());
    let at = |id: u32| plan.roots.iter().filter(|x| matches!(x.value, PlanValue::Node { id: i, .. } if i == id)).map(|x| x.name.clone()).collect::<Vec<_>>();
    if at(*id).len() > 1 && (*nullable || !same_as.is_empty() || plan.roots.iter().any(|x| matches!(&x.value, PlanValue::Node { id: i, nullable, same_as } if i == id && (*nullable || !same_as.is_empty())))) {
        return Err(gap(format!("node {id} is the roots {}, one object, and may be null or another object as well: a shared object is its own, made by its constructor", at(*id).join(" and "))));
    }
    for other in same_as {
        if other == id {
            return Err(gap(format!("node {id} names itself among the objects it may be")));
        }
        let Some(names) = Some(at(*other)).filter(|n| !n.is_empty()) else {
            return Err(gap(format!("node {id} may be node {other}, which is no root: a choice of one object is among the roots' objects")));
        };
        if class(*other) != class(*id) {
            return Err(gap(format!("node {id}, a {}, may be node {other} ({}), a {}: objects of two classes are never one", class(*id).unwrap_or_default(), names.join(", "), class(*other).unwrap_or_default())));
        }
    }
    Ok(())
}

/// The root `name` of a plan (`whose`: "the new version's"), adapted as `domain` at `path`, as the check makes it: a list (V2) named as
/// the root, never null, of objects of an application class, its domain resolved under this tool's list model
/// ([`crate::values::resolve`]). An adapted String root is refused: the String adapter takes a String parameter of a
/// check without a plan, and a plan's String root is not made yet.
fn adapted_root(whose: &str, name: &str, path: &str, domain: &crate::spec::plans::ValueDomain) -> Result<crate::spec::plans::ValueDomain, Unsupported> {
    let gap = |what: String| Unsupported::new(Part::Values, format!("{whose} root {name}: {what}"));
    if path != name {
        return Err(Unsupported::new(Part::Objects, format!("{whose} root {name} is the adapted value {path}: an adapted root is named as the root")));
    }
    // A list of Strings is named by `values::ListAdapter::new`, through `resolve`.
    if domain.kind == crate::spec::plans::ValueKind::String {
        return Err(gap("an adapted String root: the String adapter takes a String parameter of a check without a plan, and a plan's String root is not made yet".into()));
    }
    if domain.nullable {
        return Err(gap("a list that may be null: the check makes a list parameter that is never null, and a null list is not made yet".into()));
    }
    crate::values::resolve(domain).map_err(|u| gap(u.what))
}

/// The choices of a plan's roots (O2), by root name, as the harness makes them: the roots that may be null, the
/// pairs that may be one object (`same_as`), and the pairs that are (a node at two roots, the later root and the
/// first). Both versions' plans must make the same, so that their identity relations start alike.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Choices {
    pub nullable: Vec<String>,
    pub may_alias: Vec<(String, String)>,
    pub shared: Vec<(String, String)>,
}

impl Choices {
    pub fn is_empty(&self) -> bool {
        self.nullable.is_empty() && self.may_alias.is_empty() && self.shared.is_empty()
    }
}

impl std::fmt::Display for Choices {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut parts: Vec<String> = self.nullable.iter().map(|n| format!("{n} may be null")).collect();
        parts.extend(self.may_alias.iter().map(|(a, b)| format!("{b} may be {a}")));
        parts.extend(self.shared.iter().map(|(b, a)| format!("{b} is {a}")));
        if parts.is_empty() {
            write!(f, "none")
        } else {
            write!(f, "{}", parts.join(", "))
        }
    }
}

/// The choices of `plan`'s roots ([`Choices`]), in the order of its roots.
pub fn choices(plan: &ConstructionPlan) -> Choices {
    let mut out = Choices::default();
    let node_of = |name: &str| plan.roots.iter().find(|r| r.name == name).and_then(|r| if let PlanValue::Node { id, .. } = r.value { Some(id) } else { None });
    for (i, r) in plan.roots.iter().enumerate() {
        let PlanValue::Node { id, nullable, same_as } = &r.value else { continue };
        if *nullable {
            out.nullable.push(r.name.clone());
        }
        for other in same_as {
            for x in plan.roots.iter().filter(|x| x.name != r.name && node_of(&x.name) == Some(*other)) {
                out.may_alias.push((x.name.clone(), r.name.clone()));
            }
        }
        if let Some(first) = plan.roots[..i].iter().find(|x| node_of(&x.name) == Some(*id)) {
            out.shared.push((r.name.clone(), first.name.clone()));
        }
    }
    out
}

/// Every bounded array of a plan, by path, with its bound: the check bounds every array by one number, so a plan's
/// arrays must be bounded by the check's (`array_bound_problem`).
pub fn arrays(plan: &ConstructionPlan) -> Vec<(String, u32)> {
    plan.roots.iter().map(|r| &r.value).chain(plan.nodes.iter().flat_map(|n| n.args.iter())).filter_map(|v| match v {
        PlanValue::Array { path, max_length, .. } => Some((path.clone(), *max_length)),
        _ => None,
    }).collect()
}

/// Why a plan's arrays are bounded otherwise than the check's `max_array_length`, if they are: a bound that
/// differs would make the check about other arrays than the claim's.
pub fn array_bound_problem(plan: &ConstructionPlan, max_array_length: u32) -> Option<String> {
    arrays(plan).into_iter().find(|(_, n)| *n != max_array_length).map(|(path, n)| format!("the plan bounds the array {path} at {n} elements, and the check bounds every array at {max_array_length}: a bound of each array's own is not supported yet"))
}

/// What a plan makes a root: a primitive leaf of its type, or an object.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Rooted {
    Leaf(crate::classfile::Type),
    Object(crate::harness::RecordType),
    /// An adapted list (V2), its domain resolved under this tool's list model: the check makes its elements as a
    /// list parameter's, objects of its element class made by their constructor.
    List(crate::spec::plans::ValueDomain),
}

/// The root `name` of `plan`, as the harness makes it, from the classes of `cp`; none where the plan has no such
/// root. Each node is made by the constructor it names, whose arguments are its leaves and nodes in order: a leaf of
/// the parameter's type named by its path from the root (`this.capacity`), an object of the parameter's class. A
/// plan [`check_plans`] accepts, so that its values are supported.
pub fn root(cp: &crate::classpath::ClassPath, plan: &ConstructionPlan, name: &str) -> Result<Option<Rooted>, Unsupported> {
    let Some(root) = plan.roots.iter().find(|r| r.name == name) else { return Ok(None) };
    match &root.value {
        PlanValue::Leaf { path, ty } => {
            if path != name {
                return Err(Unsupported::new(Part::Objects, format!("the plan's root {name} is the leaf {path}: a primitive root's leaf is named as the root")));
            }
            let t = java_type(ty).ok_or_else(|| Unsupported::new(Part::Objects, format!("the plan's leaf {path} has type {ty}, which is no Java type")))?;
            Ok(Some(Rooted::Leaf(t)))
        }
        PlanValue::Array { path, element, .. } => {
            if path != name {
                return Err(Unsupported::new(Part::Objects, format!("the plan's root {name} is the array {path}: an array root is named as the root")));
            }
            let t = java_type(element).map(|e| crate::classfile::Type::Array(Box::new(e))).ok_or_else(|| Unsupported::new(Part::Objects, format!("the plan's array {path} has elements of type {element}, which is no Java type")))?;
            Ok(Some(Rooted::Leaf(t)))
        }
        // A node at two roots is one object, its leaves named from the first (O2).
        PlanValue::Node { id, .. } => {
            let first = plan.roots.iter().find(|r| matches!(r.value, PlanValue::Node { id: i, .. } if i == *id)).map(|r| r.name.as_str()).unwrap_or(name);
            node(cp, plan, *id, first, &mut Vec::new()).map(|r| Some(Rooted::Object(r)))
        }
        PlanValue::Adapted { path, domain } => adapted_root("the plan's", name, path, domain).map(|d| Some(Rooted::List(d))),
        other => Err(Unsupported::new(Part::Objects, format!("the plan's root {name} is {}, which check_plans refuses", value_name(other)))),
    }
}

/// The node `id` of `plan`, made at `path`; `within` are the classes it is part of, as for `equivalence::made_of`.
fn node(cp: &crate::classpath::ClassPath, plan: &ConstructionPlan, id: u32, path: &str, within: &mut Vec<String>) -> Result<crate::harness::RecordType, Unsupported> {
    let gap = |what: String| Unsupported::new(Part::Objects, what);
    let n = plan.nodes.iter().find(|n| n.id == id).ok_or_else(|| gap(format!("the plan has no node {id}")))?;
    let class = n.class.replace('.', "/");
    let Maker::Constructor { descriptor } = &n.maker else { return Err(unbuilt(&format!("node {id}'s factory maker"))) };
    let cf = cp.application(&class).map_err(|e| gap(format!("node {id}, a {}: {e}", n.class)))?.ok_or_else(|| gap(format!("node {id}'s class {} is not among the application's classes", n.class)))?;
    if cf.is_interface() || cf.is_abstract() || cf.is_enum() {
        return Err(gap(format!("node {id}'s class {} is not a concrete class made by its constructor", n.class)));
    }
    if cf.super_class.as_deref() != Some("java/lang/Object") {
        return Err(gap(format!("node {id}'s class {} extends {}; a class that extends another is not supported yet", n.class, cf.super_class.as_deref().unwrap_or("nothing").replace('/', "."))));
    }
    let constructors: Vec<String> = cf.methods.iter().filter(|m| m.is_constructor() && !m.is_private() && !m.is_synthetic()).map(|m| m.descriptor.clone()).collect();
    let Some(constructor) = cf.methods.iter().find(|m| m.is_constructor() && !m.is_private() && !m.is_synthetic() && m.descriptor == *descriptor) else {
        return Err(gap(format!("node {id}'s class {} has no constructor {descriptor} a caller can use; it has {}", n.class, if constructors.is_empty() { "none".to_string() } else { constructors.join(", ") })));
    };
    if let Some(effect) = side_effect(cp, &class, "<init>", descriptor) {
        return Err(gap(format!("node {id}'s constructor {descriptor} of {} has a side effect outside the object it makes, which is not supported: {effect}, so each object it makes would depend on those made before it", n.class)));
    }
    let parsed = constructor.parsed_descriptor().map_err(|e| gap(format!("node {id}'s constructor {descriptor}: {e}")))?;
    let names = constructor.parameter_names(&cf.pool);
    if parsed.params.len() != n.args.len() {
        return Err(gap(format!("node {id}'s constructor {descriptor} takes {} arguments, and the plan gives {}", parsed.params.len(), n.args.len())));
    }
    within.push(class.clone());
    let mut params = Vec::new();
    let mut inner = Vec::new();
    for ((pname, pt), arg) in names.iter().zip(&parsed.params).zip(&n.args) {
        let at = format!("{path}.{pname}");
        match arg {
            PlanValue::Leaf { path: leaf, ty } => {
                if leaf != &at {
                    return Err(gap(format!("node {id}'s argument {pname} is the leaf {leaf}, which the check names {at}: a leaf is named by its path from the root")));
                }
                if java_type(ty).as_ref() != Some(pt) {
                    return Err(gap(format!("node {id}'s argument {pname} is the leaf {leaf} of type {ty}, and the constructor takes a {}", pt.java_name())));
                }
            }
            PlanValue::Array { path: leaf, element, .. } => {
                if leaf != &at {
                    return Err(gap(format!("node {id}'s argument {pname} is the array {leaf}, which the check names {at}: a leaf is named by its path from the root")));
                }
                if java_type(element).map(|e| crate::classfile::Type::Array(Box::new(e))).as_ref() != Some(pt) {
                    return Err(gap(format!("node {id}'s argument {pname} is the array {leaf} of {element} elements, and the constructor takes a {}", pt.java_name())));
                }
            }
            PlanValue::Node { id: inner_id, .. } => {
                let inner_node = plan.nodes.iter().find(|x| x.id == *inner_id).ok_or_else(|| gap(format!("the plan has no node {inner_id}")))?;
                if *pt != crate::classfile::Type::Object(inner_node.class.replace('.', "/")) {
                    return Err(gap(format!("node {id}'s argument {pname} is node {inner_id}, a {}, and the constructor takes a {}", inner_node.class, pt.java_name())));
                }
                inner.push(node(cp, plan, *inner_id, &at, within)?);
            }
            other => return Err(gap(format!("node {id}'s argument {pname} is {}, which check_plans refuses", value_name(other)))),
        }
        params.push((pname.clone(), pt.clone()));
    }
    within.pop();
    let fields = crate::equivalence::fields_of(cp, &class, &mut Vec::new()).map_err(|e| gap(format!("node {id}, a {}: {e}", n.class)))?.map_err(|g| gap(format!("node {id}, a {}: {g}", n.class)))?;
    Ok(crate::harness::RecordType::made(&class, params, inner, fields))
}

/// The setup sequence of `plan` (O3), on the receiver's class `class` (an internal name) of `cp`: each call's
/// method name, descriptor, and its arguments as the flat parameters they are, named by their path
/// (`setup.0.n`). Each is a void instance method of the class with primitive parameters, whose `k`th call's
/// argument for the parameter `n` is the leaf `setup.k.n`.
pub fn setup_calls(cp: &crate::classpath::ClassPath, plan: &ConstructionPlan, class: &str) -> Result<Vec<(String, String, Vec<(String, crate::classfile::Type)>)>, Unsupported> {
    let gap = |what: String| Unsupported::new(Part::Objects, what);
    let java = class.replace('/', ".");
    let cf = cp.application(class).map_err(|e| gap(format!("the setup sequence's class {java}: {e}")))?.ok_or_else(|| gap(format!("the setup sequence's class {java} is not among the application's classes")))?;
    let mut out = Vec::new();
    for (k, call) in plan.setup.iter().enumerate() {
        let Some((name, descriptor)) = call.method.split_once('(').map(|(n, d)| (n.to_string(), format!("({d}"))) else {
            return Err(gap(format!("the setup call {} names no descriptor: it is name(descriptor), take(I)V", call.method)));
        };
        let Some(m) = cf.methods.iter().find(|m| m.name == name && m.descriptor == descriptor) else {
            return Err(gap(format!("the setup call {}: {java} has no such method", call.method)));
        };
        if m.is_static() || m.is_constructor() {
            return Err(gap(format!("the setup call {} is not an instance method of {java}, called on the receiver", call.method)));
        }
        if let Some(effect) = side_effect(cp, class, &name, &descriptor) {
            return Err(gap(format!("the setup call {} has a side effect outside the receiver, which is not supported: {effect}, an effect neither version's observations compare", call.method)));
        }
        let parsed = m.parsed_descriptor().map_err(|e| gap(format!("the setup call {}: {e}", call.method)))?;
        if parsed.ret != crate::classfile::Type::Void {
            return Err(unbuilt(&format!("the setup call {} returns {}, and comparing a setup call's result", call.method, parsed.ret.java_name())));
        }
        let names = m.parameter_names(&cf.pool);
        if parsed.params.len() != call.args.len() {
            return Err(gap(format!("the setup call {} takes {} arguments, and the plan gives {}", call.method, parsed.params.len(), call.args.len())));
        }
        let mut args = Vec::new();
        for ((pname, pt), arg) in names.iter().zip(&parsed.params).zip(&call.args) {
            let PlanValue::Leaf { path, ty } = arg else { return Err(unbuilt(&format!("the setup call {}'s argument {}, and a setup argument other than a primitive leaf", call.method, value_name(arg)))) };
            let at = format!("setup.{k}.{pname}");
            if *path != at {
                return Err(gap(format!("the setup call {}'s argument {pname} is the leaf {path}, which the check names {at}", call.method)));
            }
            if java_type(ty).as_ref() != Some(pt) || !pt.is_primitive() {
                return Err(gap(format!("the setup call {}'s argument {pname} is the leaf {path} of type {ty}, and the method takes a {}", call.method, pt.java_name())));
            }
            args.push((at, pt.clone()));
        }
        out.push((name, descriptor, args));
    }
    Ok(out)
}

/// A side effect of `class`'s method `name(descriptor)` that a construction or a setup call may not have (O2): a
/// write to a static field, in it or in an application method it reaches ([`crate::purity`]'s walk). The checks make
/// each object from the classes' initial state, so an object whose constructor changes state outside itself, a count
/// of the objects made or a registry, would be checked as the first one made only, and a static a setup call writes
/// is an effect outside every observation of the check. Calls into the JDK are not judged here: the engines refuse
/// what they don't implement (`System.out`, a clock), wherever it is. `None` where there is no such write.
pub(crate) fn side_effect(cp: &crate::classpath::ClassPath, class: &str, name: &str, descriptor: &str) -> Option<String> {
    let result = crate::purity::Purity::new(cp).analyse(class, name, descriptor);
    let write = result.violations.iter().find_map(|v| v.split_once(" writes static field ").filter(|(_, rest)| !rest.contains(' ')))?;
    Some(format!("{} writes the static field {}", write.0, write.1))
}

/// The construction of an ordinary receiver (O1): `this`, an object of `class` (an internal name) made by its
/// constructor, a named root, exactly as a parameter made by its constructor is (`equivalence::made_of`, step H2 of
/// `llm-dlc/loops/foundations-heap.md`): the one constructor a caller can use, from primitive leaves and objects made
/// so in turn, observed by its fields after the call. Asked where a regression or property check meets an instance
/// method of a class that is not a record of primitive components. A class outside that is refused by name: a
/// constructor argument the stream has yet to make (an array, a String, a dependency) says so, and what no plan of
/// this wave makes (several constructors without a choice, a superclass, a cycle) is a boundary of its own.
pub fn receiver(cp: &crate::classpath::ClassPath, class: &str) -> Result<crate::harness::RecordType, Unsupported> {
    let java = class.replace('/', ".");
    match crate::equivalence::made_of(cp, class, &mut Vec::new()) {
        Ok(Ok(record)) => Ok(record),
        Ok(Err(gap)) if gap.contains("constructor's arguments must be") || gap.contains("is an interface") || gap.contains("is abstract") => {
            Err(unbuilt(&format!("an ordinary receiver, an object of {java} made by its constructor, whose {gap}")))
        }
        Ok(Err(gap)) => Err(Unsupported::new(Part::Objects, format!("the receiver, an object of {java} made by its constructor: {gap}"))),
        Err(e) => Err(Unsupported::new(Part::Objects, format!("the receiver, an object of {java}: {e}"))),
    }
}

/// Reads `--plan FILE` of `equivalence` and `prove`: [`Plans`] as JSON (one plan for both versions of a property
/// check is `before` and `after` alike), checked by [`check_plans`].
pub fn load(path: &Path) -> Result<Plans, Unsupported> {
    let text = std::fs::read_to_string(path).map_err(|e| Unsupported::new(Part::Objects, format!("--plan {}: {e}", path.display())))?;
    let plans: Plans = serde_json::from_str(&text).map_err(|e| Unsupported::new(Part::Objects, format!("--plan {}: {e}", path.display())))?;
    check_plans(&plans.before, &plans.after)?;
    Ok(plans)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::spec::plans::{Maker, Node, PlanBounds, PlanValue, Root};

    fn plan(nodes: u32) -> ConstructionPlan {
        ConstructionPlan {
            nodes: vec![Node { id: 0, class: "shop.Money".into(), maker: Maker::Constructor { descriptor: "(J)V".into() }, args: vec![PlanValue::Leaf { path: "m.cents".into(), ty: "long".into() }] }],
            roots: vec![Root { name: "m".into(), value: PlanValue::Node { id: 0, nullable: false, same_as: Vec::new() } }],
            setup: Vec::new(),
            restrictions: Vec::new(),
            bounds: PlanBounds { nodes, max_array_length: 0, setup_calls: 0 },
        }
    }

    #[test]
    fn a_plan_of_the_shapes_a_check_makes_is_accepted_and_the_rest_refused_by_name() {
        check_plans(&plan(1), &plan(1)).unwrap();
        // A plan of the wrong shape is named as such first.
        assert!(check_plans(&plan(1), &plan(0)).unwrap_err().what.starts_with("the new version's construction plan: the plan makes 1 objects"));
        // What no check makes yet is refused in its stream's words.
        let with_arg = |value: PlanValue| {
            let mut p = plan(1);
            p.nodes[0].args = vec![value];
            p
        };
        let array = with_arg(PlanValue::Array { path: "m.cents".into(), element: "long".into(), max_length: 0, nullable: false });
        check_plans(&array, &array).unwrap();
        let null_array = with_arg(PlanValue::Array { path: "m.cents".into(), element: "long".into(), max_length: 0, nullable: true });
        assert!(check_plans(&null_array, &null_array).unwrap_err().what.contains("the objects stream builds it"));
        let twice = |p: &mut ConstructionPlan| p.nodes[0].args.push(PlanValue::Leaf { path: "m.cents".into(), ty: "long".into() });
        let mut doubled = plan(1);
        twice(&mut doubled);
        assert!(check_plans(&doubled, &doubled).unwrap_err().what.contains("one value at two paths"));
        let dependency = with_arg(PlanValue::Dependency { path: "m.rates".into(), class: "shop.Rates".into() });
        assert!(check_plans(&dependency, &dependency).unwrap_err().what.contains("dependency"));
        let mut factory = plan(1);
        factory.nodes[0].maker = Maker::Factory { method: "shop.Money#of(J)Lshop/Money;".into() };
        assert!(check_plans(&factory, &factory).unwrap_err().what.contains("factory"));
        let file = std::env::temp_dir().join(format!("plans-{}.json", std::process::id()));
        std::fs::write(&file, serde_json::to_string(&Plans { before: plan(1), after: plan(1) }).unwrap()).unwrap();
        assert_eq!(load(&file).unwrap(), Plans { before: plan(1), after: plan(1) });
        std::fs::write(&file, "{\"before\": 1}").unwrap();
        assert!(load(&file).unwrap_err().what.contains("--plan"));
        let _ = std::fs::remove_file(&file);
    }

    /// Two Money roots, `m` (node 0) and `n` (node `id`, 1 or 0 again) of the choice given, and a Pair of node 2.
    fn two(n_value: PlanValue) -> ConstructionPlan {
        let money = |id: u32, path: &str| Node { id, class: "shop.Money".into(), maker: Maker::Constructor { descriptor: "(J)V".into() }, args: vec![PlanValue::Leaf { path: format!("{path}.cents"), ty: "long".into() }] };
        let mut p = plan(2);
        p.nodes = vec![money(0, "m"), money(1, "n")];
        p.roots.push(Root { name: "n".into(), value: n_value });
        p
    }

    #[test]
    fn a_plans_roots_may_be_null_or_one_object_and_the_same_choices_inside_a_nested_object_are_refused() {
        let node = |id: u32, nullable: bool, same_as: Vec<u32>| PlanValue::Node { id, nullable, same_as };
        // A root that may be null, one that may be another root's object, and one node at two roots.
        let nullable = two(node(1, true, vec![]));
        check_plans(&nullable, &nullable).unwrap();
        assert_eq!(choices(&nullable), Choices { nullable: vec!["n".into()], ..Choices::default() });
        let may = two(node(1, false, vec![0]));
        check_plans(&may, &may).unwrap();
        assert_eq!(choices(&may).may_alias, vec![("m".to_string(), "n".to_string())]);
        let shared = two(node(0, false, vec![]));
        check_plans(&shared, &shared).unwrap();
        assert_eq!(choices(&shared).shared, vec![("n".to_string(), "m".to_string())]);
        // Both versions make the same choices.
        let what = check_plans(&may, &shared).unwrap_err().what;
        assert!(what.contains("choices of null and of one object differ: n may be m before, n is m now"), "{what}");
        // A shared node has no choice besides; a choice names another root's node of the same class.
        assert!(check_plans(&two(node(0, true, vec![])), &two(node(0, true, vec![]))).unwrap_err().what.contains("a shared object is its own"));
        assert!(check_plans(&two(node(1, false, vec![1])), &two(node(1, false, vec![1]))).unwrap_err().what.contains("names itself"));
        let mut other_class = two(node(1, false, vec![0]));
        other_class.nodes[1].class = "shop.Fee".into();
        let what = check_plans(&other_class, &other_class).unwrap_err().what;
        assert!(what.contains("which is not of its class shop.Fee"), "the shape names it first: {what}");
        // The receiver is never null.
        let mut this = plan(1);
        this.roots[0] = Root { name: "this".into(), value: node(0, true, vec![]) };
        assert!(check_plans(&this, &this).unwrap_err().what.contains("the receiver of an instance method is never null"));
        // Inside a nested object: a choice, or a node shared with a root or another argument, is refused by name.
        let pair = |args: Vec<PlanValue>, roots: Vec<Root>| {
            let mut p = two(node(1, false, vec![]));
            p.nodes.push(Node { id: 2, class: "shop.Pair".into(), maker: Maker::Constructor { descriptor: "(Lshop/Money;Lshop/Money;)V".into() }, args });
            p.roots = roots;
            p.bounds.nodes = 3;
            p
        };
        let root = |name: &str, id: u32| Root { name: name.into(), value: node(id, false, vec![]) };
        let nested_null = pair(vec![node(0, true, vec![]), node(1, false, vec![])], vec![root("p", 2)]);
        assert!(check_plans(&nested_null, &nested_null).unwrap_err().what.contains("a choice inside a nested object"));
        let nested_twice = pair(vec![node(0, false, vec![]), node(0, false, vec![])], vec![root("p", 2)]);
        assert!(check_plans(&nested_twice, &nested_twice).unwrap_err().what.contains("a plan's nested shared nodes"));
        let with_root = pair(vec![node(0, false, vec![]), node(1, false, vec![])], vec![root("p", 2), root("m", 0)]);
        assert!(check_plans(&with_root, &with_root).unwrap_err().what.contains("shared between a root and a nested object"));
        let ok = pair(vec![node(0, false, vec![]), node(1, false, vec![])], vec![root("p", 2)]);
        check_plans(&ok, &ok).unwrap();
    }
}
