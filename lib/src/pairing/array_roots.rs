//! A paired property with bounded int-array roots, scalar int arguments and an explicit observation.
//! The entry to the checker and the JVM replay has only scalar arguments. Each target call gets a fresh
//! heap reconstructed from those arguments, including the null and identity choices in the layout.

use std::fmt::Write;
use std::path::{Path, PathBuf};

use crate::classfile::{ClassFile, Insn, Method, Type};
use crate::equivalence::Options;
use crate::harness::{self, Layout};
use crate::spec::{Derivation, ExternalInput, Observation, PreservationContract, StatementSpec};
use crate::statement::{AssumptionKind, Statement};

pub(super) struct ArrayRoots {
    layout: Layout,
    names: Vec<String>,
    groups: Vec<Vec<String>>,
    bound: usize,
}

#[derive(serde::Deserialize)]
struct Projection {
    observations: Vec<Observation>,
    values: Vec<serde_json::Value>,
}

/// This overlap runs with both engines. All target state is in the input arrays and the method locals.
pub(crate) fn closed(class: &ClassFile, method: &Method) -> bool {
    if class.super_class.as_deref() != Some("java/lang/Object") || !class.interfaces.is_empty() || class.method("<clinit>", "()V").is_some() {
        return false;
    }
    let Some(code) = &method.code else { return false };
    code.instructions().is_ok_and(|insns| insns.iter().all(|(_, op)| !matches!(op,
        Insn::GetStatic(_) | Insn::PutStatic(_) | Insn::GetField(_) | Insn::PutField(_) | Insn::InvokeDynamic(_)
        | Insn::InvokeStatic(_) | Insn::InvokeVirtual(_) | Insn::InvokeInterface(_) | Insn::InvokeSpecial(_) | Insn::New(_))))
}

impl ArrayRoots {
    pub(super) fn plan(options: &Options, names: &[String], types: &[Type], ret: &Type) -> Result<Self, String> {
        let is_array = |t: &Type| matches!(t, Type::Array(element) if **element == Type::Int);
        let arrays = types.iter().filter(|t| is_array(t)).count();
        if arrays == 0 || types.iter().any(|t| !is_array(t) && *t != Type::Int) || *ret != Type::Int {
            return Err("the selected-observation profile takes int[] and int parameters, including at least one array, and an int result".into());
        }
        if options.cache.is_some() || options.object_domain.is_some() {
            return Err("the paired int-array profile has no cache identity or constructor-object domain".into());
        }
        if options.unchanged_unless.is_some() || options.lemmas.is_some() || !options.observed_initializers.is_empty() || !options.requested_models.is_empty() || options.confirm {
            return Err("the paired array profile supports a root precondition and one engine per run; the requested scope, models, lemmas or confirmation have no lowering".into());
        }
        if options.may_alias.iter().any(|(a, b)| a == b) {
            return Err("--may-alias needs two different parameters".into());
        }
        let groups = harness::alias_groups(&options.may_alias, names);
        let mut layout = Layout::plain(names, types);
        layout.choose_arrays(&options.nullable, &groups)?;
        let bound = options.max_array_length as usize;
        if bound as u64 * arrays as u64 + types.len() as u64 + layout.flags().len() as u64 > 255 {
            return Err("the array length and cell choices exceed the JVM limit of 255 parameter slots".into());
        }
        let array_name = |name: &str| names.iter().zip(types).any(|(n, t)| n == name && is_array(t));
        for (index, observation) in options.selected_observations.iter().enumerate() {
            if options.selected_observations[..index].contains(observation) {
                return Err(format!("duplicate selected observation {}", observation.id()));
            }
            match observation {
                Observation::Result | Observation::Exception => {}
                Observation::ArrayParameter { parameter } if array_name(parameter) => {}
                Observation::Identity { left, right } if array_name(left) && array_name(right) => {}
                other => return Err(format!("the paired int-array observer cannot examine {}", other.id())),
            }
        }
        Ok(Self { layout, names: names.to_vec(), groups, bound })
    }

    fn inputs(&self) -> &[harness::Param] {
        &self.layout.params[..self.names.len()]
    }

    fn arguments(&self, prefix: &str) -> String {
        (0..self.names.len()).map(|i| format!("{prefix}{i}")).collect::<Vec<_>>().join(", ")
    }

    fn parameters(&self) -> Vec<(String, &'static str)> {
        let mut flat = Vec::new();
        for (root, parameter) in self.inputs().iter().enumerate() {
            if parameter.ty == Type::Int {
                flat.push((format!("arg{root}"), "int"));
                continue;
            }
            flat.push((format!("len{root}"), "int"));
            flat.extend((0..self.bound).map(|i| (format!("cell{root}_{i}"), "int")));
        }
        flat.extend(self.layout.flags().iter().map(|index| (format!("flag{index}"), "boolean")));
        flat
    }

    pub(super) fn precondition(&self) -> String {
        let args = self.parameters().into_iter().map(|(n, _)| n).collect::<Vec<_>>().join(", ");
        format!("RegressionPair.admitted({args})")
    }

    pub(super) fn decode(&self, flat: &[crate::witness::Typed]) -> Result<Vec<crate::witness::Typed>, crate::Error> {
        let value = |name: &str| flat.iter().find(|p| p.name == name).and_then(|p| p.value.as_ref());
        let missing = || crate::Error::new("the witness does not encode the planned int-array roots");
        let mut flags = std::collections::BTreeMap::new();
        for i in self.layout.flags() {
            flags.insert(i, value(&format!("flag{i}")).and_then(|v| v.as_bool()).ok_or_else(missing)?);
        }
        let roots = self.layout.made_roots(&|i| flags[&i], true);
        let mut inputs = Vec::new();
        for (i, parameter) in self.inputs().iter().enumerate() {
            let name = &parameter.name;
            if parameter.ty == Type::Int {
                let number = value(&format!("arg{i}")).and_then(|v| v.as_i64()).and_then(|n| i32::try_from(n).ok()).ok_or_else(missing)?;
                inputs.push(crate::witness::Typed { name: name.clone(), ty: "int".into(), value: Some(number.into()), components: None, from: None });
                continue;
            }
            let (_, made) = roots.iter().find(|(n, _)| n == name).ok_or_else(missing)?;
            let data = match made {
                harness::Made::Null => serde_json::Value::Null,
                harness::Made::Same(other) => serde_json::json!({ "same": self.names.iter().position(|n| n == other).ok_or_else(missing)? }),
                harness::Made::Own => {
                    let length = value(&format!("len{i}")).and_then(|v| v.as_u64()).filter(|n| *n <= self.bound as u64).ok_or_else(missing)?;
                    let cells: Result<Vec<_>, _> = (0..length).map(|j| value(&format!("cell{i}_{j}")).and_then(|v| v.as_i64()).ok_or_else(missing)).collect();
                    serde_json::json!(cells?)
                }
            };
            inputs.push(crate::witness::Typed { name: name.clone(), ty: "int[]".into(), value: Some(data), components: None, from: None });
        }
        Ok(inputs)
    }

    fn roots(&self, prefix: &str) -> String {
        let mut out = String::new();
        for (i, parameter) in self.inputs().iter().enumerate() {
            if parameter.ty == Type::Int {
                writeln!(out, "        int {prefix}{i} = arg{i};").unwrap();
                continue;
            }
            let name = &parameter.name;
            let mut values = vec![format!("len{i}")];
            values.extend((0..self.bound).map(|j| format!("cell{i}_{j}")));
            let mut value = format!("data({})", values.join(", "));
            if let Some(choice) = self.layout.choice(name) {
                for (earlier, flag) in choice.same.iter().rev() {
                    let index = self.names.iter().position(|n| n == earlier).expect("layout root");
                    value = format!("flag{flag} && {prefix}{index} != null ? {prefix}{index} : {value}");
                }
                if let Some(flag) = choice.null {
                    value = format!("flag{flag} ? null : {value}");
                }
            }
            writeln!(out, "        int[] {prefix}{i} = {value};").unwrap();
        }
        out
    }

    fn invocation(&self, prefix: &str, owner: &str, method: &str) -> String {
        let mut s = self.roots(prefix);
        writeln!(s, "        int {prefix}Result = 0; Throwable {prefix}Failure = null;").unwrap();
        let args = self.arguments(prefix);
        writeln!(s, "        try {{ {prefix}Result = {owner}.{method}({args}); }} catch (Throwable e) {{ {prefix}Failure = e; }}").unwrap();
        s
    }

    pub(super) fn source(&self, options: &Options, class: &str, method: &str) -> String {
        let flat = self.parameters().into_iter().map(|(n, t)| format!("{t} {n}")).collect::<Vec<_>>().join(", ");
        let fields: Vec<_> = (0..self.bound).map(|i| format!("v{i}")).collect();
        let mut data_args = vec!["int length".into()];
        data_args.extend(fields.iter().map(|n| format!("int {n}")));
        let mut s = String::from("public final class RegressionPair {\n");
        writeln!(s, "    static int[] data({}) {{\n        switch (length) {{", data_args.join(", ")).unwrap();
        for n in 1..=self.bound {
            writeln!(s, "            case {n}: return new int[] {{ {} }};", fields[..n].join(", ")).unwrap();
        }
        s.push_str("            default: return new int[0];\n        }\n    }\n");
        let signature = self.inputs().iter().map(|p| format!("{} {}", p.ty.java_name(), p.name)).collect::<Vec<_>>().join(", ");
        writeln!(s, "    static boolean accepts({signature}) {{ return {}; }}", options.assume.as_deref().unwrap_or("true")).unwrap();
        writeln!(s, "    public static boolean admitted({flat}) {{").unwrap();
        let invalid = self.inputs().iter().enumerate().filter(|(_, p)| p.ty != Type::Int)
            .map(|(i, _)| format!("len{i} < 0 || len{i} > {}", self.bound)).collect::<Vec<_>>().join(" || ");
        writeln!(s, "        if ({invalid}) return false;").unwrap();
        s.push_str(&self.roots("d"));
        writeln!(s, "        return accepts({});\n    }}", self.arguments("d")).unwrap();
        s.push_str("    static boolean sameCells(int[] x, int[] y) {\n        if (x == y) return true;\n        if (x == null || y == null || x.length != y.length) return false;\n        for (int i = 0; i < x.length; i++) if (x[i] != y[i]) return false;\n        return true;\n    }\n");
        writeln!(s, "    public static boolean agree({flat}) {{").unwrap();
        let before = self.invocation("a", &format!("before.{class}"), method);
        let after = self.invocation("b", class, method);
        s.push_str(&before);
        s.push_str(&after);
        let index = |n: &str| self.names.iter().position(|p| p == n).expect("validated observation");
        let projection = options.selected_observations.iter().map(|observation| match observation {
            Observation::Result => "(aFailure == null ? bFailure == null && aResult == bResult : bFailure != null)".into(),
            Observation::Exception => "(aFailure == null ? bFailure == null : bFailure != null && aFailure.getClass() == bFailure.getClass())".into(),
            Observation::ArrayParameter { parameter } => format!("sameCells(a{0}, b{0})", index(parameter)),
            Observation::Identity { left, right } => format!("((a{0} == a{1}) == (b{0} == b{1}))", index(left), index(right)),
            _ => unreachable!("validated observation"),
        }).collect::<Vec<_>>();
        writeln!(s, "        return {};\n    }}", projection.join(" && ")).unwrap();
        // The JVM witness runner can return a char array. Encode an ordered JSON array of the actual
        // selected values. These methods are separate entries and the symbolic check never calls them.
        let descriptors = serde_json::to_string(&options.selected_observations).expect("observation descriptors");
        let header = serde_json::to_string(&format!("{{\"observations\":{descriptors},\"values\":[")).unwrap();
        for (prefix, call) in [("a", before), ("b", after)] {
            writeln!(s, "    public static char[] observe{prefix}({flat}) {{").unwrap();
            s.push_str(&call);
            let values = options.selected_observations.iter().map(|obs| match obs {
                Observation::Result => format!("({prefix}Failure == null ? Integer.toString({prefix}Result) : \"null\")"),
                Observation::Exception => format!("({prefix}Failure == null ? \"null\" : \"\\\"\" + {prefix}Failure.getClass().getName() + \"\\\"\")"),
                Observation::ArrayParameter { parameter } => format!("java.util.Arrays.toString({prefix}{})", index(parameter)),
                Observation::Identity { left, right } => format!("({prefix}{} == {prefix}{})", index(left), index(right)),
                _ => unreachable!("validated observation"),
            }).collect::<Vec<_>>();
            writeln!(s, "        return ({header} + {} + \"]}}\").toCharArray();\n    }}", values.join(" + \",\" + ")).unwrap();
        }
        s.push_str("}\n");
        s
    }

    pub(super) fn replay(&self, options: &Options, witness: &crate::property::Counterexample, work: &Path, class: &str,
                         method: &Method, entries: &[PathBuf]) -> Result<crate::equivalence::Counterexample, String> {
        use crate::{interp::Value, jbmc::Argument, jvm_witness};
        let inputs = self.decode(&witness.inputs).map_err(|e| e.to_string())?;
        let mut types = Vec::new();
        let mut arguments = Vec::new();
        let mut descriptor = String::from("(");
        for (name, ty) in self.parameters() {
            let value = witness.inputs.iter().find(|p| p.name == name).and_then(|p| p.value.as_ref())
                .ok_or_else(|| format!("the witness has no primitive value for {name}"))?;
            let (kind, code, number) = if ty == "boolean" {
                (Type::Boolean, 'Z', value.as_bool().map(i32::from))
            } else {
                (Type::Int, 'I', value.as_i64().and_then(|n| i32::try_from(n).ok()))
            };
            types.push(kind);
            descriptor.push(code);
            arguments.push(Argument::Scalar(Value::Int(number.ok_or_else(|| format!("invalid {ty} witness for {name}"))?)));
        }
        descriptor.push_str(")[C");
        let calls = ["observea", "observeb"].map(|name| jvm_witness::DirectCall {
            owner: super::CLASS.into(), name: name.into(), descriptor: descriptor.clone(), ret: Type::Array(Box::new(Type::Char)),
        });
        let slots = (0..types.len() as u16).collect::<Vec<_>>();
        let run = jvm_witness::run(&work.join("root-replay"), harness::PROPERTY_CLASS, &types, &slots, &arguments, &calls, entries)?;
        if run.check != jvm_witness::Check::Refuted || run.calls.len() != 2 {
            return Err(format!("the JVM did not refute the selected array comparison ({:?})", run.check));
        }
        let projections = |call: &crate::witness::Replayed| -> Result<Projection, String> {
            let units: Option<Vec<u16>> = call.result_array.as_ref().and_then(|a| a.iter().map(|v| match v {
                Value::Int(n) => u16::try_from(*n).ok(), _ => None,
            }).collect());
            let text = String::from_utf16(&units.ok_or("the JVM returned no projection")?).map_err(|e| e.to_string())?;
            let projection: Projection = serde_json::from_str(&text).map_err(|e| format!("unreadable JVM projection: {e}"))?;
            if projection.observations != options.selected_observations || projection.values.len() != projection.observations.len() {
                return Err("the JVM did not examine the requested observation descriptors".into());
            }
            Ok(projection)
        };
        let (old, new) = (projections(&run.calls[0])?, projections(&run.calls[1])?);
        let differs: Vec<_> = old.values.iter().zip(&new.values).zip(&options.selected_observations)
            .filter(|((a, b), _)| a != b).map(|(_, o)| o.id()).collect();
        if differs.is_empty() { return Err("the selected post-call values agreed on the JVM".into()); }
        let values: Vec<_> = inputs.iter().map(|p| format!("{}={}", p.name, p.value.as_ref().unwrap())).collect();
        let mut call = witness.call.clone();
        call.class = class.replace('/', ".");
        call.class_file = format!("{class}.class");
        call.method.clone_from(&method.name);
        call.descriptor.clone_from(&method.descriptor);
        call.arguments = inputs.clone();
        let mut previous_call = call.clone();
        previous_call.classes = "before".into();
        let show = |values: &[serde_json::Value]| options.selected_observations.iter().zip(values).map(|(o, v)| format!("{}={v}", o.id())).collect::<Vec<_>>().join(", ");
        Ok(crate::equivalence::Counterexample {
            input: format!("{}({})", method.name, values.join(", ")), before: show(&old.values), after: show(&new.values),
            values, found: witness.found.clone(), shrink_runs: witness.shrink_runs, inputs,
            found_inputs: witness.found_inputs.as_ref().map(|v| self.decode(v)).transpose().map_err(|e| e.to_string())?,
            call, previous_call: Some(previous_call), differs, replay_observations: old.observations, jvm: Some(run.jdk),
        })
    }

    pub(super) fn describe(&self, options: &Options, statement: &mut Statement) {
        let selected = &options.selected_observations;
        let params = self.inputs();
        statement.kind = "regression".into();
        statement.domain = crate::statement::plain_domain_of(params, options.max_array_length, &options.nullable, &self.groups);
        statement.bounds.max_array_length = Some(options.max_array_length);
        statement.assumptions.retain_mut(|a| {
            if a.kind != AssumptionKind::Precondition { return true; }
            if let Some(condition) = &options.assume {
                a.text.clone_from(condition);
                return true;
            }
            false
        });
        statement.observations.result = if selected.contains(&Observation::Result) { "return value and whether one was returned" } else { "unselected" }.into();
        statement.observations.exceptions = if selected.contains(&Observation::Exception) { "same exception class or normal completion" } else { "unselected" }.into();
        statement.observations.arrays = selected.iter().filter_map(|o| match o { Observation::ArrayParameter { parameter } => Some(parameter.clone()), _ => None }).collect();
        statement.observations.identities = selected.iter().filter_map(|o| match o { Observation::Identity { left, right } => Some(format!("{left} == {right}")), _ => None }).collect();
        statement.spec = Some(StatementSpec {
            contract: PreservationContract {
                subject: options.target.clone(),
                inputs: params.iter().map(|p| ExternalInput { name: p.name.clone(), ty: p.ty.java_name(), derivation: Derivation::Identity }).collect(),
                required: selected.iter().map(Observation::id).collect(), approved_changes: Vec::new(),
            },
            observations: selected.clone(), domain: None, correspondence: None, environment: None, summaries: Vec::new(),
        });
    }
}
