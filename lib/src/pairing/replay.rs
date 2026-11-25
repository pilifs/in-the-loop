//! Reconstruct a scalar paired counterexample from calls on two unmodified deployments.

use std::path::Path;

use crate::classfile::{ClassFile, Method, Type};
use crate::equivalence::Counterexample;
use crate::harness::{self, expr, Layout, PropertyHarness};
use crate::interp::Value;
use crate::jbmc::Argument;
use crate::jvm_witness::{self, Check, DirectCall, Run};
use crate::relocate::Previous;
use crate::witness::{self, Replayed};

pub(crate) fn integral(ty: &Type) -> bool {
    matches!(ty, Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long)
}

/// A boolean expression evaluated on the concrete JVM operands. A call, an unavailable
/// operand or an exceptional evaluation leaves the replay open.
fn boolean(expression: &expr::Expr, locals: &[Value]) -> Option<bool> {
    match expr::eval_with(expression, locals, &[]).ok()? {
        Value::Int(0) => Some(false),
        Value::Int(1) => Some(true),
        _ => None,
    }
}

pub(crate) fn regression_holds(harness: &harness::Harness, arguments: &[Argument], old: &Replayed, new: &Replayed) -> Option<bool> {
    let (mut locals, _) = witness::locals_of(&harness.params, arguments, &[]);
    if let Some(scope) = &harness.scope {
        if boolean(scope, &locals)? { return Some(true); }
    }
    let (before, current) = (old.returned?, new.returned?);
    let Some(relation) = &harness.relation else { return Some(before == current) };
    // Use the very slots and expression compiled into EquivalenceHarness. Wide values occupy two slots.
    locals.resize(usize::from(relation.previous.max(relation.result).max(relation.slots_end)) + 2, Value::Int(0));
    locals[usize::from(relation.previous)] = before;
    locals[usize::from(relation.result)] = current;
    boolean(&relation.expr, &locals)
}

pub(crate) struct ScalarPair<'a> {
    call: DirectCall,
    scope: Option<&'a str>,
    pub witness: Option<Counterexample>,
}

impl<'a> ScalarPair<'a> {
    pub fn for_method(class: &ClassFile, method: &Method, scope: Option<&'a str>) -> Option<Self> {
        let signature = method.parsed_descriptor().ok()?;
        if !method.is_public() || !method.is_static() || class.access & crate::classfile::flags::PUBLIC == 0
            || !signature.params.iter().all(integral) || !integral(&signature.ret) {
            return None;
        }
        Some(Self { call: DirectCall { owner: class.name.clone(), name: method.name.clone(), descriptor: method.descriptor.clone(), ret: signature.ret },
                    scope, witness: None })
    }

    pub fn replay(&mut self, dir: &Path, original: &Previous, layout: &Layout, harness: &PropertyHarness,
                  arguments: &[Argument]) -> Result<Run, String> {
        let types = layout.types();
        let slots: Vec<_> = layout.params.iter().map(|p| p.slot).collect();
        let (mut locals, _) = witness::locals_of(&harness.params, arguments, &[]);
        let admitted = match &harness.assume {
            None => true,
            Some(e) => boolean(e, &locals).ok_or("cannot evaluate the complete paired assumption on the original witness")?,
        };
        // The generated Java guard treats an exception as outside the intended change. A guard
        // outside the input-expression evaluator is left open rather than guessed from one release.
        let exempt = match self.scope {
            None => false,
            Some(text) => {
                let scope = expr::parse(text, &harness.params).map_err(|_| "the intended-change guard needs its own original JVM evaluation")?;
                boolean(&scope, &locals).ok_or("cannot evaluate the complete intended-change guard on the original witness")?
            }
        };
        let mut agrees = None;
        let run = jvm_witness::original_pair(dir, &types, &slots, arguments,
            [(&self.call, &original.classpath), (&self.call, &original.current_classpath)], |old, new| {
                let result = exempt || old.returned? == new.returned?;
                agrees = Some(result);
                locals.push(Value::Int(i32::from(result)));
                Some(!admitted || boolean(&harness.assertion, &locals)?)
            })?;
        let agrees = agrees.ok_or("the original return values were unavailable")?;
        if run.check == Check::Refuted {
            let target = witness::Target { class_internal: &self.call.owner, method: &self.call.name, descriptor: &self.call.descriptor,
                                           is_static: true, classes: "after" };
            let (input, values) = witness::call_in(&self.call.name, layout, arguments);
            self.witness = Some(Counterexample {
                input, before: run.calls[0].outcome.clone(), after: run.calls[1].outcome.clone(), values, found: None,
                shrink_runs: 0, inputs: witness::typed_inputs(&layout.params, arguments), found_inputs: None,
                call: witness::typed_call(&target, layout, arguments, false, &[]),
                previous_call: Some(witness::typed_call(&witness::Target { classes: "before", ..target }, layout, arguments, true, &[])),
                differs: vec!["result".into()], replay_observations: Vec::new(), jvm: Some(run.jdk.clone()),
            });
        }
        // The nested property is about RegressionPair.agree; the outer witness above carries both public calls.
        let result = Replayed { outcome: agrees.to_string(), returned: Some(Value::Int(i32::from(agrees))), ..Default::default() };
        Ok(Run { jdk: run.jdk, check: run.check, calls: vec![result] })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness::{Harness, Param, Relation};

    #[test]
    fn original_scalar_witness_checks_the_scope_and_wide_result_relation() {
        let input = Param { name: "skip".into(), ty: Type::Boolean, slot: 0 };
        let params = [input.clone(), Param { name: "previous".into(), ty: Type::Long, slot: 3 },
                      Param { name: "result".into(), ty: Type::Long, slot: 6 }];
        let relation = Relation { expr: expr::parse("previous + 1L == result", &params).unwrap(), previous: 3, result: 6,
            slots_end: 8, previous_components: None, result_components: None, previous_object: None, result_object: None,
            previous_objects: Vec::new() };
        let harness = Harness { bytes: vec![], probe: vec![], source: String::new(), scope: Some(expr::parse("skip", &params).unwrap()),
                                params: vec![input], before_args: None, relation: Some(relation) };
        let returned = |v| Replayed { returned: Some(Value::Long(v)), ..Default::default() };
        let check = |skip, old, new| regression_holds(&harness, &[Argument::Scalar(Value::Int(skip))], &old, &new);
        assert_eq!(check(0, returned(i64::MAX), returned(i64::MIN)), Some(true));
        assert_eq!(check(0, returned(65), returned(65)), Some(false));
        assert_eq!(check(1, returned(65), returned(65)), Some(true));
        assert_eq!(check(0, Replayed::default(), returned(65)), None);
    }
}
