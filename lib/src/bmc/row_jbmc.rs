//! Encode one direct primitive-row array using independent scalar inputs for JBMC.
//! Choose a fresh row at its first live occurrence and an earlier index for each
//! repetition. This represents every bounded graph, including equal distinct rows.

use std::fmt::Write as _;
use std::path::Path;
use crate::classfile::Type;
use crate::classpath::ClassPath;
use crate::harness::Param;
use crate::jbmc::{Ending, JbmcResult, PrimitiveRow};
use crate::interp::Value;
use crate::Verdict;

fn suffix(ty: &Type) -> char {
    match ty { Type::Long => 'j', Type::Double => 'd', Type::Float => 'f', _ => 'i' }
}

struct RowSlots {
    alias: Option<u32>,
    length: u32,
    cells: Vec<u32>,
}

pub(crate) struct Plan {
    pub class: String,
    root: u32,
    height: u32,
    scalar_slots: Vec<(u32, u32)>,
    rows: Vec<RowSlots>,
    element: Type,
    nullable: bool,
}

impl Plan {
    pub fn prepare(cp: &ClassPath, params: &[Param], bound: u32, nullable: bool, dir: &Path) -> Result<Self, String> {
        let root = params.iter().find(|p| super::reference_inputs::row_element(&p.ty).is_some()).ok_or("missing row parameter")?;
        let element = super::reference_inputs::row_element(&root.ty).unwrap().clone();
        let mut class = String::from("RaggedPropertyInput");
        while cp.exists(&class) { class.push('$'); }
        let mut formals = Vec::new();
        let mut next = 0u32;
        let mut slot = |ty: &Type| {
            let index = next;
            formals.push(format!("{} arg{index}{}", ty.java_name(), suffix(ty)));
            next += u32::from(ty.slots());
            index
        };
        let mut scalar_slots = Vec::new();
        let mut arguments = Vec::new();
        for p in params {
            if p.slot == root.slot { arguments.push("rows".into()); continue; }
            if !p.ty.is_primitive() { return Err("ragged inputs with another reference parameter".into()); }
            let flat = slot(&p.ty);
            scalar_slots.push((u32::from(p.slot), flat));
            arguments.push(format!("arg{flat}{}", suffix(&p.ty)));
        }
        let height = slot(&Type::Int);
        let mut rows = Vec::new();
        for i in 0..bound {
            rows.push(RowSlots { alias: (i > 0).then(|| slot(&Type::Int)), length: slot(&Type::Int),
                cells: (0..bound).map(|_| slot(&element)).collect() });
        }
        if next > 255 { return Err(format!("ragged JBMC entry needs {next} primitive parameter slots at bound {bound}; a JVM method admits 255")); }
        let word = element.java_name();
        let cell_suffix = suffix(&element);
        let mut src = format!("public class {class} {{\n public static void check({}) {{\n", formals.join(", "));
        let low = if nullable { -1 } else { 0 };
        writeln!(src, "  if (arg{height}i < {low} || arg{height}i > {bound}) return;").unwrap();
        writeln!(src, "  {word}[][] rows = arg{height}i < 0 ? null : new {word}[arg{height}i][];").unwrap();
        for (i, row) in rows.iter().enumerate() {
            writeln!(src, "  if (arg{height}i > {i}) {{").unwrap();
            if let Some(a) = row.alias {
                writeln!(src, "   if (arg{a}i >= 0 && arg{a}i < {i}) rows[{i}] = rows[arg{a}i]; else {{").unwrap();
            }
            let n = row.length;
            writeln!(src, "   if (arg{n}i < -1 || arg{n}i > {bound}) return;\n   if (arg{n}i >= 0) {{").unwrap();
            writeln!(src, "    rows[{i}] = new {word}[arg{n}i];").unwrap();
            for (j, cell) in row.cells.iter().enumerate() {
                writeln!(src, "    if (arg{n}i > {j}) rows[{i}][{j}] = arg{cell}{cell_suffix};").unwrap();
            }
            src.push_str("   }\n");
            if row.alias.is_some() { src.push_str("   }\n"); }
            src.push_str("  }\n");
        }
        writeln!(src, "  {}.{}({});\n }}\n}}", crate::harness::PROPERTY_CLASS, crate::harness::METHOD, arguments.join(", ")).unwrap();
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
        let file = dir.join(format!("{class}.java"));
        std::fs::write(&file, src).map_err(|e| e.to_string())?;
        let javac = crate::jimage::JImage::find_java_home().ok_or("no JDK for the ragged JBMC input harness")?.join("bin/javac");
        let harness = dir.parent().unwrap_or(dir).join("harness");
        // The adjacent Java rendering describes PropertyHarness. Its classfile
        // is the executable claim, so javac must use that classfile unchanged.
        let run = std::process::Command::new(javac).args(["-proc:none", "-implicit:none", "-g", "-parameters", "-sourcepath"]).arg(dir).arg("-cp").arg(harness)
            .arg("-d").arg(dir).arg(file).output().map_err(|e| e.to_string())?;
        if !run.status.success() { return Err(String::from_utf8_lossy(&run.stderr).into_owned()); }
        Ok(Self { class, root: u32::from(root.slot), height, scalar_slots, rows, element, nullable })
    }

    /// Translate only an actual, complete scalar trace. The ordinary replay,
    /// including the original JVM, receives the user's original row graph.
    pub fn project(&self, result: &mut JbmcResult) {
        if result.verdict != Verdict::Violation { return; }
        if let Err(why) = self.project_witness(result) {
            result.verdict = Verdict::Unverifiable;
            result.ending = Ending::Unreadable;
            result.problem = Some(format!("ragged JBMC witness: {why}"));
        }
    }

    fn project_witness(&self, result: &mut JbmcResult) -> Result<(), String> {
        let get = |s: u32| result.raw_inputs.get(&s).ok_or_else(|| format!("missing primitive input slot {s}"));
        let int = |s: u32| get(s)?.parse::<i32>().map_err(|_| format!("invalid int in slot {s}"));
        let h = int(self.height)?;
        if h < (if self.nullable { -1 } else { 0 }) || h > self.rows.len() as i32 { return Err("outer length outside the bound".into()); }
        let mut graph: Vec<PrimitiveRow> = Vec::new();
        for slots in self.rows.iter().take(h.max(0) as usize) {
            if let Some(alias) = slots.alias {
                let i = int(alias)?;
                if i >= 0 && (i as usize) < graph.len() {
                    let row = match &graph[i as usize] {
                        PrimitiveRow::Null => PrimitiveRow::Null,
                        PrimitiveRow::Same(first) => PrimitiveRow::Same(*first),
                        PrimitiveRow::Cells(_) => PrimitiveRow::Same(i as usize),
                    };
                    graph.push(row);
                    continue;
                }
            }
            let n = int(slots.length)?;
            if n < -1 || n > slots.cells.len() as i32 { return Err("inner length outside the bound".into()); }
            let row = if n == -1 { PrimitiveRow::Null } else {
                let cells = slots.cells[..n as usize].iter().map(|&s| {
                    crate::jbmc::parse_value(&self.element, get(s)?).map_err(|e| e.to_string())
                }).collect::<Result<Vec<Value>, String>>()?;
                PrimitiveRow::Cells(cells)
            };
            graph.push(row);
        }
        let scalars = self.scalar_slots.iter().map(|&(old, flat)| Ok((old, get(flat)?.clone())))
            .collect::<Result<_, String>>()?;
        result.raw_inputs = scalars;
        result.raw_arrays.insert(self.root, (h >= 0).then(|| graph.iter().map(|r| r.json(&self.element).to_string()).collect()));
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::jbmc::parse_json;

    #[test]
    fn row_projection_preserves_identity_and_requires_the_live_scalar_trace() {
        let plan = Plan {
            class: "Inputs".into(), root: 0, height: 0, scalar_slots: vec![], element: Type::Long, nullable: true,
            rows: vec![
                RowSlots { alias: None, length: 1, cells: vec![2, 4, 6] },
                RowSlots { alias: Some(8), length: 9, cells: vec![10, 12, 14] },
                RowSlots { alias: Some(16), length: 17, cells: vec![18, 20, 22] },
            ],
        };
        let mut result = parse_json("", "PropertyHarness", "check", 7, None);
        let value = "9007199254740993";
        result.raw_inputs = [(0, "3"), (1, "1"), (2, value), (8, "-1"), (9, "1"), (10, value), (16, "0")]
            .into_iter().map(|(slot, s)| (slot, s.to_string())).collect();
        let mut missing = result.clone();
        missing.raw_inputs.remove(&10);
        missing.verdict = Verdict::Violation;
        plan.project(&mut missing);
        assert_eq!(missing.verdict, Verdict::Unverifiable);
        assert!(missing.problem.unwrap().contains("slot 10"));
        plan.project_witness(&mut result).unwrap();
        let rows = result.raw_arrays[&0].as_ref().unwrap();
        assert_eq!(rows, &[format!("[\"{value}\"]"), format!("[\"{value}\"]"), r#"{"sameCell":0}"#.into()]);
        for (height, expected) in [("-1", None), ("0", Some(vec![]))] {
            result.raw_inputs.insert(0, height.into());
            plan.project_witness(&mut result).unwrap();
            assert_eq!(result.raw_arrays[&0], expected);
        }
    }
}
