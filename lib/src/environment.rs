//! The environment stream's module (`llm-dlc/loops/application-core-environment.md`): modelled dependency outcomes
//! ([`CallModel`]): consumed primitive returns, modelled failures, and constructor-made nullable DTOs, under one
//! declared environment for both versions. Registered by Phase 0 of `llm-dlc/loops/application-core.md`, so that
//! the stream starts without editing a shared file. Until the stream builds a model, [`check_model`] returns
//! [`Unsupported`] naming it, and the effect check refuses the claim: no model is checked as a normal return.

use std::path::Path;

use crate::spec::plans::CallModel;
use crate::spec::{ModeledCall, Part, Unsupported};

/// Checks that the effect check can make `call`'s stubs give the results `model` says, under its coupling and
/// bound. Called by the effect check (`effects`) for every modelled call with a model.
pub fn check_model(call: &ModeledCall, model: &CallModel) -> Result<(), Unsupported> {
    let _ = model;
    let short = call.call.split('(').next().unwrap_or(&call.call).replace('/', ".");
    Err(Unsupported::new(Part::Environment, format!("a modelled call's model of its results ({short}): the environment stream builds it (llm-dlc/loops/application-core-environment.md)")))
}

/// Reads `--environment FILE` of `effects` and `compare`: the modelled calls a person declares, as a JSON list of
/// [`ModeledCall`], each with its model; checked by [`check_model`].
pub fn load(path: &Path) -> Result<Vec<ModeledCall>, Unsupported> {
    let text = std::fs::read_to_string(path).map_err(|e| Unsupported::new(Part::Environment, format!("--environment {}: {e}", path.display())))?;
    let calls: Vec<ModeledCall> = serde_json::from_str(&text).map_err(|e| Unsupported::new(Part::Environment, format!("--environment {}: {e}", path.display())))?;
    declared(&calls).map_err(|u| Unsupported::new(Part::Environment, format!("--environment {}: {}", path.display(), u.what)))?;
    Ok(calls)
}

/// Checks the modelled calls a person declares (`--environment`, `compare::Options::environment`): each has a model
/// [`check_model`] accepts. Called by `effects::check_builds` before any entry point is checked.
pub fn declared(calls: &[ModeledCall]) -> Result<(), Unsupported> {
    for call in calls {
        match &call.model {
            Some(model) => check_model(call, model)?,
            None => return Err(Unsupported::new(Part::Environment, format!("the call {} has no model; one with none is the entry point's own, from its spec", call.call))),
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::spec::plans::{Coupling, ModelledResult, Returned};

    #[test]
    fn a_model_is_refused_by_name_until_the_stream_builds_it() {
        let model = CallModel { id: "rates".into(), key: vec!["arg0".into()], coupling: Coupling::Query, results: vec![ModelledResult::Returns { value: Returned::Primitive { ty: "long".into() } }], bound: 2 };
        let call = ModeledCall { call: "shop/Rates#rate(Ljava/lang/String;)J".into(), outcomes: vec!["returns".into()], model: Some(model.clone()) };
        let gap = check_model(&call, &model).unwrap_err();
        assert_eq!(gap.part, Part::Environment);
        assert!(gap.what.contains("(shop.Rates#rate)") && gap.what.contains("the environment stream builds it"), "{gap}");
        let file = std::env::temp_dir().join(format!("environment-{}.json", std::process::id()));
        std::fs::write(&file, serde_json::to_string(&[call.clone()]).unwrap()).unwrap();
        assert!(load(&file).unwrap_err().what.contains("the environment stream builds it"));
        std::fs::write(&file, serde_json::to_string(&[ModeledCall { model: None, ..call }]).unwrap()).unwrap();
        assert!(load(&file).unwrap_err().what.contains("has no model"));
        let _ = std::fs::remove_file(&file);
    }
}
