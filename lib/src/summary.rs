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
//! **An effect contract** (a declaration with `writes:` in the same file). For an instance method: the fields of its
//! receiver and object parameters it writes (`prove --writes`, [`crate::property::Options::writes`]), proved with
//! its frame (every other field of those inputs is what it was, and nothing else that was there before the call is
//! written) and also shown to read nothing that was there before the call: no field of its receiver or its object
//! arguments, no static field that is not final, no array, and to compare no such object by identity
//! ([`crate::bmc::Options::closed_frame`]). What it writes is then a function of its arguments alone, so in the check
//! a call of it, by anything but the harness and the claim, on a receiver of exactly its class and on arguments
//! within the bounds it was proved at (a String not null and no longer than the bound, an object not null), makes the
//! writes the contract states and nothing else: a field its assertion gives a parameter's value as `this.f == p`
//! takes it, and any other written field any value of its primitive type ([`crate::bmc::Effect`]). Elsewhere the
//! method runs as written. A written field of a reference type the assertion gives no parameter's value is refused:
//! the stub cannot make any object. It returns, with any value of its integral or boolean result, or none.
//!
//! All are Java the tool writes into the claim's class ([`crate::harness::expr::CLAIM_CLASS`]) and javac compiles
//! with the claim's expressions; the checker runs them as it runs the target. What bytecode cannot say is a call
//! of the checker's intrinsics ([`crate::gap_contracts::INTRINSICS`]): any value, a path no run takes, a proof that
//! does not go through.

use crate::classfile::Type;
use crate::classpath::ClassPath;
use crate::harness::Param;

/// The intrinsics the generated members call, as a class javac compiles them against. The checker answers the
/// calls itself, and the class is not kept.
pub const INTRINSICS_SOURCE: &str = "package jvmcontract;\n\npublic final class GapIntrinsics {\n    private GapIntrinsics() {\n    }\n\n    public static native int anyInt();\n\n    public static native long anyLong();\n\n    public static native boolean anyBoolean();\n\n    public static native void effect(int index);\n\n    public static native void infeasible();\n\n    public static native void unproved();\n}\n";

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

/// The instance method an effect contract is about: its class, name and descriptor, its parameters by name (their
/// slots as the method's own, the receiver's not counted), and its result.
#[derive(Debug, Clone)]
pub struct EffectSignature {
    pub class: String,
    pub name: String,
    pub descriptor: String,
    pub params: Vec<Param>,
    pub ret: Type,
}

impl EffectSignature {
    /// The signature of `target`, a public instance method of a public class that the claim's class can call and an
    /// effect contract can stand in for: or why it is not one.
    pub fn of(cp: &ClassPath, target: &str) -> Result<EffectSignature, String> {
        let (class_internal, _) = crate::verifier::parse_target(target).ok_or("a target is <class>#<method>")?;
        let class = cp.application(&class_internal).map_err(|e| e.to_string())?.ok_or_else(|| format!("class not found: {}", class_internal.replace('/', ".")))?;
        let method = crate::verifier::select_method(&class, target)?;
        let descriptor = method.parsed_descriptor().map_err(|e| e.to_string())?;
        let signature = EffectSignature { class: class_internal, name: method.name.clone(), descriptor: method.descriptor.clone(), params: crate::harness::params(&method.parameter_names(&class.pool), &descriptor.params), ret: descriptor.ret };
        if method.is_static() || method.name == "<init>" || !method.is_public() || class.access & crate::classfile::flags::PUBLIC == 0 {
            return Err(format!("{target} is not a public instance method of a public class"));
        }
        if let Some(p) = signature.params.iter().find(|p| matches!(p.ty, Type::Array(_))) {
            return Err(format!("parameter {} has type {}, and an effect contract is over primitives, Strings and objects", p.name, p.ty.java_name()));
        }
        if signature.ret != Type::Void {
            any(&signature.ret)?;
        }
        Ok(signature)
    }

    /// The stub's local that holds the parameter `name`: the receiver is its first, `this`.
    fn local(&self, name: &str) -> Option<(usize, Type)> {
        if name == "this" {
            return Some((0, Type::Object(self.class.clone())));
        }
        self.params.iter().find(|p| p.name == name).map(|p| (1 + p.slot as usize, p.ty.clone()))
    }

    /// The stub's descriptor: the receiver first, then the method's own parameters.
    pub fn stub_descriptor(&self) -> String {
        format!("(L{};{}", self.class, &self.descriptor[1..])
    }
}

/// The writes of an effect contract at a call: each name of `writes` (`this.f` or `p.f`, a field the class of the
/// receiver or of the object parameter `p` declares), with the parameter the assertion's top-level conjunct
/// `this.f == q` gives it, of the field's own type; with none, a field of a primitive type takes any value, and one
/// of a reference type is refused.
pub fn effect_writes(cp: &ClassPath, signature: &EffectSignature, writes: &[String], assertion: Option<&str>) -> Result<Vec<crate::bmc::EffectWrite>, String> {
    let pins: Vec<(String, String)> = assertion.map(conjuncts).unwrap_or_default().into_iter().filter_map(|c| c.split_once("==").map(|(l, r)| (l.trim().to_string(), r.trim().to_string()))).collect();
    let mut out = Vec::new();
    for name in writes {
        let (object, field) = name.split_once('.').filter(|(_, f)| !f.contains('.')).ok_or_else(|| format!("{name} is no field of the receiver or an object parameter"))?;
        let (local, ty) = signature.local(object).ok_or_else(|| format!("{name}: {object} is no parameter of {}", signature.name))?;
        let Type::Object(owner) = ty.clone() else { return Err(format!("{name}: {object} is no object")) };
        let class = cp.application(&owner).map_err(|e| e.to_string())?.ok_or_else(|| format!("{name}: class not found: {}", owner.replace('/', ".")))?;
        let descriptor = class.field(field).map(|f| f.descriptor.clone()).ok_or_else(|| format!("{name}: {} declares no field {field}", owner.replace('/', ".")))?;
        let value = pins.iter().filter(|(l, _)| l == name).find_map(|(_, r)| signature.local(r).filter(|(_, t)| t.descriptor() == descriptor).map(|(slot, _)| slot));
        if value.is_none() && (descriptor.starts_with('L') || descriptor.starts_with('[') || matches!(descriptor.as_str(), "F" | "D")) {
            return Err(format!("{name} is written and the assertion gives it no parameter's value (a top-level `{name} == p`, p of its type): at a call the contract leaves a field it writes any value of its type, and of {} there is no such value to give", crate::classfile::Type::parse(&descriptor).map(|t| t.java_name()).unwrap_or(descriptor.clone())));
        }
        out.push(crate::bmc::EffectWrite { object: local, owner, field: field.to_string(), descriptor, value });
    }
    Ok(out)
}

/// The top-level conjuncts of a Java boolean expression, each without the parentheses around it.
fn conjuncts(expression: &str) -> Vec<String> {
    let (mut out, mut depth, mut quoted, mut start) = (Vec::new(), 0i32, None::<char>, 0);
    let chars: Vec<(usize, char)> = expression.char_indices().collect();
    let mut i = 0;
    while i < chars.len() {
        let (at, c) = chars[i];
        match (quoted, c) {
            (Some(q), '\\') if q == '"' || q == '\'' => i += 1,
            (Some(q), c) if c == q => quoted = None,
            (Some(_), _) => {}
            (None, '"' | '\'') => quoted = Some(c),
            (None, '(') => depth += 1,
            (None, ')') => depth -= 1,
            (None, '&') if depth == 0 && chars.get(i + 1).is_some_and(|&(_, d)| d == '&') => {
                out.push(expression[start..at].to_string());
                start = at + 2;
                i += 1;
            }
            _ => {}
        }
        i += 1;
    }
    out.push(expression[start..].to_string());
    out.into_iter().map(|c| strip_parentheses(c.trim()).to_string()).collect()
}

/// The expression without the parentheses that enclose all of it.
fn strip_parentheses(e: &str) -> &str {
    let mut e = e;
    while e.starts_with('(') && e.ends_with(')') {
        let mut depth = 0;
        let encloses = e.char_indices().all(|(i, c)| {
            match c {
                '(' => depth += 1,
                ')' => depth -= 1,
                _ => {}
            }
            depth > 0 || i == e.len() - 1
        });
        if !encloses {
            break;
        }
        e = e[1..e.len() - 1].trim();
    }
    e
}

/// The name of the stub that stands in for the calls of the `i`th effect contract's method.
pub fn effect_stub(i: usize) -> String {
    format!("effect{i}")
}

/// The member of the claim's class for the `i`th effect contract, proved at `bound`: the stub that runs in place of
/// the method's calls, the receiver its first parameter.
pub fn effect(i: usize, signature: &EffectSignature, bound: u32) -> Result<String, String> {
    let stub = effect_stub(i);
    let class = signature.class.replace(['/', '$'], ".");
    let list = std::iter::once(format!("{class} self")).chain(signature.params.iter().map(|p| format!("{} {}", p.ty.java_name(), p.name))).collect::<Vec<_>>().join(", ");
    let arguments = signature.params.iter().map(|p| p.name.clone()).collect::<Vec<_>>().join(", ");
    let mut within = Vec::new();
    for p in &signature.params {
        if crate::values::is_string(&p.ty) {
            within.push(format!("{0} != null && {0}.length() <= {bound}", p.name));
        } else if !p.ty.is_primitive() {
            within.push(format!("{} != null", p.name));
        }
    }
    let within = if within.is_empty() { "true".to_string() } else { within.join(" && ") };
    let (ret, as_written, returns) = if signature.ret == Type::Void {
        ("void".to_string(), format!("self.{}({arguments});\n            return;", signature.name), String::new())
    } else {
        (signature.ret.java_name(), format!("return self.{}({arguments});", signature.name), format!("\n        return {};", any(&signature.ret)?))
    };
    Ok(format!(
        r#"
    /**
     * The effect contract of {class}.{name}, proved beside this check: on arguments within the bounds it was proved
     * at, the writes it states and nothing else; on any other, the method as written.
     */
    public static {ret} {stub}({list}) {{
        if (!({within})) {{
            {as_written}
        }}
        jvmcontract.GapIntrinsics.effect({i});{returns}
    }}
"#,
        name = signature.name
    ))
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
    fn an_effect_contract_is_used_within_its_bounds_and_runs_the_method_as_written_elsewhere() {
        let string = Type::Object("java/lang/String".into());
        let names = vec!["name".to_string(), "count".to_string(), "owner".to_string()];
        let types = vec![string, Type::Long, Type::Object("a/b/Owner".into())];
        let s = EffectSignature { class: "a/b/Outer$Bean".into(), name: "rename".into(), descriptor: "(Ljava/lang/String;JLa/b/Owner;)V".into(), params: crate::harness::params(&names, &types), ret: Type::Void };
        let stub = effect(1, &s, 3).unwrap();
        assert!(stub.contains("public static void effect1(a.b.Outer.Bean self, java.lang.String name, long count, a.b.Owner owner) {\n        if (!(name != null && name.length() <= 3 && owner != null)) {\n            self.rename(name, count, owner);\n            return;\n        }\n        jvmcontract.GapIntrinsics.effect(1);\n    }"), "{stub}");
        assert_eq!(s.stub_descriptor(), "(La/b/Outer$Bean;Ljava/lang/String;JLa/b/Owner;)V");
        // The receiver is the stub's first local; a long takes two.
        assert_eq!(s.local("this").map(|(slot, _)| slot), Some(0));
        assert_eq!(s.local("owner").map(|(slot, _)| slot), Some(4));
        let int = EffectSignature { ret: Type::Int, ..s };
        assert!(effect(0, &int, 3).unwrap().contains("return self.rename(name, count, owner);\n        }\n        jvmcontract.GapIntrinsics.effect(0);\n        return jvmcontract.GapIntrinsics.anyInt();"));
    }

    #[test]
    fn the_conjuncts_of_an_assertion_are_split_at_the_top_level_alone() {
        assert_eq!(conjuncts("(this.a == a) && this.b == \\old(this.b)"), ["this.a == a", "this.b == \\old(this.b)"]);
        assert_eq!(conjuncts("(x && y) || z && w.equals(\"&&\")"), ["(x && y) || z", "w.equals(\"&&\")"]);
        assert_eq!(conjuncts("((p))"), ["p"]);
        assert_eq!(conjuncts("(a) == (b)"), ["(a) == (b)"]);
    }

    #[test]
    fn a_parameter_or_a_result_a_summary_cannot_state_is_refused_by_name() {
        let array = signature(&[("a", Type::Array(Box::new(Type::Int)))], Type::Int);
        assert!(summary(0, &array, 8, None, "result == 0").unwrap_err().contains("parameter a has type int[]"));
        let object = signature(&[("n", Type::Int)], Type::Object("java/lang/String".into()));
        assert!(induction(&object, 8, false, &[], "n").unwrap_err().contains("the result has type java.lang.String"));
    }
}
