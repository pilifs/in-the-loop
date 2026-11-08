//! The objects stream's module (`llm-dlc/loops/application-core-objects.md`): the common construction plan
//! ([`ConstructionPlan`]) of receivers, parameters, bounded arrays and short setup sequences, fed through
//! `equivalence`, `prove` and `compare`. Registered by Phase 0 of `llm-dlc/loops/application-core.md`, so that the
//! stream starts without editing a shared file. Until the stream builds a part, its entry point returns
//! [`Unsupported`] naming it, and every call site refuses the claim that needs it: no plan falls back to the
//! constructor domain the checks make today.

use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::spec::plans::ConstructionPlan;
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
pub fn check_plans(before: &ConstructionPlan, after: &ConstructionPlan) -> Result<(), Unsupported> {
    for (version, plan) in [("previous", before), ("new", after)] {
        if let Some(problem) = plan.shape_problem() {
            return Err(Unsupported::new(Part::Objects, format!("the {version} version's construction plan: {problem}")));
        }
    }
    Err(unbuilt("a domain made by a construction plan"))
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
    fn every_entry_point_is_refused_by_name_until_the_stream_builds_it() {
        let gap = check_plans(&plan(1), &plan(1)).unwrap_err();
        assert_eq!(gap.part, Part::Objects);
        assert!(gap.what.contains("the objects stream builds it"), "{gap}");
        // A plan of the wrong shape is named as such first.
        assert!(check_plans(&plan(1), &plan(0)).unwrap_err().what.starts_with("the new version's construction plan: the plan makes 1 objects"));
        let file = std::env::temp_dir().join(format!("plans-{}.json", std::process::id()));
        std::fs::write(&file, serde_json::to_string(&Plans { before: plan(1), after: plan(1) }).unwrap()).unwrap();
        assert!(load(&file).unwrap_err().what.contains("the objects stream builds it"));
        std::fs::write(&file, "{\"before\": 1}").unwrap();
        assert!(load(&file).unwrap_err().what.contains("--plan"));
        let _ = std::fs::remove_file(&file);
    }
}
