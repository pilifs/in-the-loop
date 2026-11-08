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
/// [`MAX_SETUP_CALLS`] calls on the receiver, of primitive leaves (`setup.0.n`), the same in both versions. What it
/// doesn't make yet is refused by its stream's name, before any check: a bounded array, a node that may be null or
/// one of several, one object at two paths, a factory, a dependency (the objects stream's), and an adapted String or
/// list (the values stream's adapter).
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
        for (at, value) in plan.roots.iter().map(|r| (r.name.clone(), &r.value)).chain(plan.nodes.iter().flat_map(|n| n.args.iter().map(move |a| (format!("node {}", n.id), a)))) {
            supported(version, &at, value, &mut used)?;
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
        if !plan.setup.is_empty() && !plan.roots.iter().any(|r| r.name == "this") {
            return Err(Unsupported::new(Part::Objects, format!("the {version} version's plan has a setup sequence and no receiver: setup calls are made on this")));
        }
    }
    let names = |p: &ConstructionPlan| p.roots.iter().map(|r| r.name.clone()).collect::<Vec<_>>();
    if names(before) != names(after) {
        return Err(Unsupported::new(Part::Objects, format!("the plans' roots differ: {} before, {} now; both versions are given the same inputs", names(before).join(", "), names(after).join(", "))));
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
        PlanValue::Array { path, .. } => Err(unbuilt(&format!("the {version} version's {at} takes the bounded array {path}, and a construction of arrays"))),
        PlanValue::Adapted { path, .. } => Err(Unsupported::new(Part::Values, format!("the {version} version's {at} takes {path}, an adapted value: the values stream builds it (llm-dlc/loops/application-core-values.md)"))),
        PlanValue::Dependency { path, class } => Err(unbuilt(&format!("the {version} version's {at} takes {path}, a dependency of {class} the environment model stands for, and a construction with dependencies"))),
        PlanValue::Node { id, nullable, same_as } => {
            if *nullable || !same_as.is_empty() {
                return Err(unbuilt(&format!("the {version} version's {at} is node {id}, which may be null or one of several, and a plan's choice of null or of one object")));
            }
            if used.contains(id) {
                return Err(unbuilt(&format!("the {version} version's {at} is node {id} again, one object at two paths, and a plan's shared nodes")));
            }
            used.push(*id);
            Ok(())
        }
    }
}

/// What a plan makes a root: a primitive leaf of its type, or an object.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Rooted {
    Leaf(crate::classfile::Type),
    Object(crate::harness::RecordType),
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
        PlanValue::Node { id, .. } => node(cp, plan, *id, name, &mut Vec::new()).map(|r| Some(Rooted::Object(r))),
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
        assert!(check_plans(&array, &array).unwrap_err().what.contains("the objects stream builds it"));
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
}
