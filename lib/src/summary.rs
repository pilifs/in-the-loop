//! Checked summaries of static methods, and proofs by induction on a measure.
//!
//! A method that calls itself on every path is unrolled by the checker call by call, and a matcher with a
//! wildcard doubles its paths with every character (Spring's `PatternMatchUtils.simpleMatch`). The way out is the
//! one a person takes: prove once what the method computes, by induction, and use that statement wherever it is
//! called.
//!
//! **Induction** (`prove --decreases EXPR`, a declaration's `decreases:`). The property is checked on the method's
//! body, where each call of the method by anything but the harness runs the hypothesis instead: the call's
//! arguments are within the property's assumption and the check's bounds, and `EXPR` on them (an int over the
//! parameters) is at least zero and below `EXPR` on the arguments of the call under proof, or the proof does not go
//! through and the check ends with no verdict; the call then returns any value the property's assertion holds of.
//! That is strong induction on the measure: the property holds of the calls the hypothesis is used on because
//! their measure is a smaller natural number.
//!
//! **A summary** (`prove --lemmas FILE`, a properties file). Each declaration is proved first, at the check's own
//! bounds, as above when it has a `decreases:`. In the check itself a call of its method, by anything but the
//! harness and the claim, runs the summary: where the arguments are within the declaration's assumption and the
//! bounds it was proved at (a String not null and no longer than the bound), the call returns any value the
//! declaration's assertion holds of, and elsewhere the method runs as written. A summary states a result and no
//! effect, so the proof of one also shows the method has none a caller could see, and that its result does not
//! depend on which objects its arguments are ([`crate::bmc::Options::pure`]); it is refused otherwise. A
//! summarized method is a public static method of a public class (the claim's class calls it where the summary
//! does not apply), over primitives and Strings, with a primitive result.
//!
//! Both are Java the tool writes into the claim's class ([`crate::harness::expr::CLAIM_CLASS`]) and javac compiles
//! with the claim's expressions; the checker runs them as it runs the target. What bytecode cannot say is a call
//! of the checker's intrinsics ([`crate::gap_contracts::INTRINSICS`]): any value, a path no run takes, a proof that
//! does not go through.

use crate::classfile::Type;
use crate::classpath::ClassPath;
use crate::harness::Param;

/// The intrinsics the generated members call, as a class javac compiles them against. The checker answers the
/// calls itself, and the class is not kept.
pub const INTRINSICS_SOURCE: &str = "package jvmcontract;\n\npublic final class GapIntrinsics {\n    private GapIntrinsics() {\n    }\n\n    public static native int anyInt();\n\n    public static native long anyLong();\n\n    public static native boolean anyBoolean();\n\n    public static native void infeasible();\n\n    public static native void unproved();\n}\n";

/// The method a declaration is about: its class, name and descriptor, its parameters by name, and its result.
#[derive(Debug, Clone)]
pub struct Signature {
    pub class: String,
    pub name: String,
    pub descriptor: String,
    pub params: Vec<Param>,
    pub ret: Type,
}

impl Signature {
    /// The signature of `target` (`pkg.Class#method`), a static method the claim's class can call and a summary
    /// can state: or why it is not one.
    pub fn of(cp: &ClassPath, target: &str) -> Result<Signature, String> {
        let (class_internal, _) = crate::verifier::parse_target(target).ok_or("a target is <class>#<method>")?;
        let class = cp.application(&class_internal).map_err(|e| e.to_string())?.ok_or_else(|| format!("class not found: {}", class_internal.replace('/', ".")))?;
        let method = crate::verifier::select_method(&class, target)?;
        let descriptor = method.parsed_descriptor().map_err(|e| e.to_string())?;
        let signature = Signature { class: class_internal, name: method.name.clone(), descriptor: method.descriptor.clone(), params: crate::harness::params(&method.parameter_names(&class.pool), &descriptor.params), ret: descriptor.ret };
        if !method.is_static() || !method.is_public() || class.access & crate::classfile::flags::PUBLIC == 0 {
            return Err(format!("{target} is not a public static method of a public class"));
        }
        guard(&signature.params, 0)?;
        any(&signature.ret)?;
        Ok(signature)
    }

    fn list(&self) -> String {
        self.params.iter().map(|p| format!("{} {}", p.ty.java_name(), p.name)).collect::<Vec<_>>().join(", ")
    }

    fn arguments(&self) -> String {
        self.params.iter().map(|p| p.name.clone()).collect::<Vec<_>>().join(", ")
    }

    fn arguments_and(&self, last: &str) -> String {
        self.params.iter().map(|p| p.name.as_str()).chain([last]).collect::<Vec<_>>().join(", ")
    }
}

/// What makes arguments ones a proof at `bound` was about: every String not null and of at most `bound` units.
fn guard(params: &[Param], bound: u32) -> Result<String, String> {
    let mut parts = Vec::new();
    for p in params {
        if crate::values::is_string(&p.ty) {
            parts.push(format!("{0} != null && {0}.length() <= {bound}", p.name));
        } else if !p.ty.is_primitive() || matches!(p.ty, Type::Float | Type::Double) {
            return Err(format!("parameter {} has type {}, and a summary or an induction hypothesis is over integral and boolean parameters and Strings", p.name, p.ty.java_name()));
        }
    }
    Ok(if parts.is_empty() { "true".into() } else { parts.join(" && ") })
}

/// Any value of the result's type, as Java.
fn any(ret: &Type) -> Result<String, String> {
    Ok(match ret {
        Type::Boolean => "jvmcontract.GapIntrinsics.anyBoolean()".into(),
        Type::Int => "jvmcontract.GapIntrinsics.anyInt()".into(),
        Type::Long => "jvmcontract.GapIntrinsics.anyLong()".into(),
        Type::Byte | Type::Short | Type::Char => format!("({}) jvmcontract.GapIntrinsics.anyInt()", ret.java_name()),
        other => return Err(format!("the result has type {}, and a summary or an induction hypothesis states an integral or boolean result", other.java_name())),
    })
}

/// The name of the stub that is the induction hypothesis.
pub const HYPOTHESIS: &str = "hypothesis";

/// The name of the method the harness calls, in its assumption, to keep the measure of the call under proof.
pub const ENTER: &str = "enter";

/// The name of the stub that is the summary of the `i`th lemma.
pub fn stub(i: usize) -> String {
    format!("lemma{i}")
}

/// The members of the claim's class for a proof by induction on `measure`: the claim's own `assume` (when
/// `assumes`) and `holds` are beside them.
pub fn induction(signature: &Signature, bound: u32, assumes: bool, thrown: &[String], measure: &str) -> Result<String, String> {
    let (list, arguments, ret) = (signature.list(), signature.arguments(), signature.ret.java_name());
    let within = guard(&signature.params, bound)?;
    let within = if assumes { format!("{within} && assume({arguments})") } else { within };
    // The hypothesis returns, so it says nothing of a call the property says throws (`thrown`: the claim's methods
    // for the conditions of its throws clauses): there the proof does not go through.
    let within = thrown.iter().fold(within, |within, condition| format!("{within} && !{condition}({arguments})"));
    let any = any(&signature.ret)?;
    let holds = signature.arguments_and("$result");
    Ok(format!(
        r#"
    /** The measure of the call under proof. */
    private static int $outer;

    public static int measure({list}) {{
        return {measure};
    }}

    public static boolean {ENTER}({list}) {{
        $outer = measure({arguments});
        return true;
    }}

    /**
     * The induction hypothesis, in place of a call the method makes of itself: on arguments within the assumption
     * and the bounds on which no throws clause says the call throws, whose measure is at least zero and below the
     * measure of the call under proof, any result the assertion holds of. On any other arguments the proof does
     * not go through.
     */
    public static {ret} {HYPOTHESIS}({list}) {{
        if (!({within})) {{
            jvmcontract.GapIntrinsics.unproved();
        }}
        int $measure = measure({arguments});
        if ($measure < 0 || $measure >= $outer) {{
            jvmcontract.GapIntrinsics.unproved();
        }}
        {ret} $result = {any};
        if (!holds({holds})) {{
            jvmcontract.GapIntrinsics.infeasible();
        }}
        return $result;
    }}
"#
    ))
}

/// The members of the claim's class for the summary of the `i`th lemma, proved at `bound`: its assumption and
/// assertion as methods, and the stub that runs in place of the method's calls.
pub fn summary(i: usize, signature: &Signature, bound: u32, assume: Option<&str>, assertion: &str) -> Result<String, String> {
    let (list, arguments, ret, stub) = (signature.list(), signature.arguments(), signature.ret.java_name(), stub(i));
    let within = guard(&signature.params, bound)?;
    let any = any(&signature.ret)?;
    let holds = signature.arguments_and("$result");
    let original = format!("{}.{}", signature.class.replace(['/', '$'], "."), signature.name);
    let assume = assume.unwrap_or("true");
    // A method of no parameters has a lemma too: its assertion is over the result alone.
    let with_result = if list.is_empty() { format!("{ret} {result}", result = crate::harness::RESULT) } else { format!("{list}, {ret} {result}", result = crate::harness::RESULT) };
    Ok(format!(
        r#"
    public static boolean {stub}_assume({list}) {{
        return {assume};
    }}

    public static boolean {stub}_holds({with_result}) {{
        return {assertion};
    }}

    /**
     * The summary of {original}, proved beside this check: on arguments within its assumption and the bounds it was
     * proved at, any result its assertion holds of; on any other, the method as written.
     */
    public static {ret} {stub}({list}) {{
        if (!({within} && {stub}_assume({arguments}))) {{
            return {original}({arguments});
        }}
        {ret} $result = {any};
        if (!{stub}_holds({holds})) {{
            jvmcontract.GapIntrinsics.infeasible();
        }}
        return $result;
    }}
"#
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn signature(params: &[(&str, Type)], ret: Type) -> Signature {
        let names: Vec<String> = params.iter().map(|(n, _)| n.to_string()).collect();
        let types: Vec<Type> = params.iter().map(|(_, t)| t.clone()).collect();
        Signature { class: "a/b/Outer$Glob".into(), name: "matches".into(), descriptor: String::new(), params: crate::harness::params(&names, &types), ret }
    }

    #[test]
    fn a_summary_applies_within_the_bound_it_was_proved_at_and_runs_the_method_elsewhere() {
        let string = Type::Object("java/lang/String".into());
        let s = signature(&[("pattern", string.clone()), ("from", Type::Int), ("text", string)], Type::Boolean);
        let members = summary(2, &s, 8, Some("from >= 0"), "result == text.startsWith(pattern, from)").unwrap();
        assert!(members.contains("if (!(pattern != null && pattern.length() <= 8 && text != null && text.length() <= 8 && lemma2_assume(pattern, from, text))) {\n            return a.b.Outer.Glob.matches(pattern, from, text);"), "{members}");
        assert!(members.contains("boolean $result = jvmcontract.GapIntrinsics.anyBoolean();\n        if (!lemma2_holds(pattern, from, text, $result)) {\n            jvmcontract.GapIntrinsics.infeasible();"), "{members}");
        assert!(members.contains("public static boolean lemma2_holds(java.lang.String pattern, int from, java.lang.String text, boolean result) {\n        return result == text.startsWith(pattern, from);"), "{members}");
    }

    #[test]
    fn a_hypothesis_asks_for_the_assumption_the_bounds_and_a_smaller_measure_of_at_least_zero() {
        let s = signature(&[("n", Type::Int)], Type::Long);
        let members = induction(&s, 8, true, &[], "n").unwrap();
        assert!(members.contains("if (!(true && assume(n))) {\n            jvmcontract.GapIntrinsics.unproved();"), "{members}");
        assert!(members.contains("if ($measure < 0 || $measure >= $outer) {\n            jvmcontract.GapIntrinsics.unproved();"), "{members}");
        assert!(members.contains("long $result = jvmcontract.GapIntrinsics.anyLong();\n        if (!holds(n, $result)) {"), "{members}");
        // With no assumption the hypothesis asks for the bounds alone.
        assert!(induction(&s, 8, false, &[], "n").unwrap().contains("if (!(true)) {"));
        // The hypothesis returns: where a throws clause says the call throws, it does not cover the call.
        let thrown = ["thrown0".to_string(), "thrown1".to_string()];
        assert!(induction(&s, 8, true, &thrown, "n").unwrap().contains("if (!(true && assume(n) && !thrown0(n) && !thrown1(n))) {\n            jvmcontract.GapIntrinsics.unproved();"));
    }

    #[test]
    fn a_method_of_no_parameters_has_a_summary_over_its_result_alone() {
        let s = signature(&[], Type::Int);
        let members = summary(0, &s, 8, None, "result == 7").unwrap();
        assert!(members.contains("public static boolean lemma0_assume() {"), "{members}");
        assert!(members.contains("public static boolean lemma0_holds(int result) {\n        return result == 7;"), "{members}");
        assert!(members.contains("if (!lemma0_holds($result)) {"), "{members}");
    }

    #[test]
    fn a_parameter_or_a_result_a_summary_cannot_state_is_refused_by_name() {
        let array = signature(&[("a", Type::Array(Box::new(Type::Int)))], Type::Int);
        assert!(summary(0, &array, 8, None, "result == 0").unwrap_err().contains("parameter a has type int[]"));
        let object = signature(&[("n", Type::Int)], Type::Object("java/lang/String".into()));
        assert!(induction(&object, 8, false, &[], "n").unwrap_err().contains("the result has type java.lang.String"));
    }
}
