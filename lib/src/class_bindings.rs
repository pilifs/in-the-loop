//! The class bindings of a prepared revision, answered in one process: for each class asked about, the exact class
//! file the checker inspects on an ordered class path and the bound runtime ([`ClassPath::bind`]), or the typed
//! refusal; for a method asked about, whether that class file declares it; and, for a JAR asked about, which entry
//! stands for each logical name. `jvmcontract class-bindings` is the command; the target workflow asks once for a
//! verifier launch, whatever the number of sides, classes or selectors.
//!
//! The request, JSON:
//!
//! ```json
//! {"sides": {"fix": {"classpath": ["prepare/fix/app.jar", "prepare/fix/dep.jar"],
//!                    "classes": [{"class": "fixture.Gate", "method": "marker", "descriptor": "()I"}],
//!                    "listEntries": [0]}}}
//! ```
//!
//! The runtime is the process's: `JAVA_HOME`, `JVMCONTRACT_JAR_RELEASE` for the release multi-release lookup is
//! bound to, and `JVMCONTRACT_CLASS_OBSERVATIONS` for what a JVM was seen to load.

use std::collections::BTreeMap;
use std::path::Path;

use serde::Deserialize;
use serde_json::{json, Value};

use crate::classfile::ClassFile;
use crate::classpath::ClassPath;
use crate::Error;

pub const SCHEMA: &str = "jvmcontract-class-bindings/v1";

#[derive(Deserialize)]
pub struct Request {
    pub sides: BTreeMap<String, Side>,
}

#[derive(Deserialize)]
pub struct Side {
    /// The class path, in order: directories and JARs.
    pub classpath: Vec<String>,
    #[serde(default)]
    pub classes: Vec<Asked>,
    /// Positions in `classpath` of the JARs whose logical entries are wanted.
    #[serde(default, rename = "listEntries")]
    pub list_entries: Vec<usize>,
    /// Ask whether the stock command can inspect the same application members on this release.
    #[serde(default, rename = "qualifyStock")]
    pub qualify_stock: bool,
}

#[derive(Deserialize)]
pub struct Asked {
    /// The class, dotted or in internal form.
    pub class: String,
    #[serde(default)]
    pub method: Option<String>,
    /// The method's JVM descriptor; without it every overload is listed and none is chosen.
    #[serde(default)]
    pub descriptor: Option<String>,
}

/// The answer to a request: every side's bindings in the order asked.
pub fn answer(request: &Request) -> Result<Value, Error> {
    let mut sides = serde_json::Map::new();
    let mut bound = None;
    for (name, side) in &request.sides {
        let mut cp = ClassPath::new();
        for entry in &side.classpath {
            cp.add(Path::new(entry))?;
        }
        let cp = cp.with_default_jdk();
        bound = cp.bound_release();
        let bindings: Vec<Value> = side.classes.iter().map(|asked| bind(&cp, asked)).collect::<Result<_, _>>()?;
        let mut entries = serde_json::Map::new();
        for &index in &side.list_entries {
            let Some((manifest, logical)) = cp.logical_entries(index) else {
                return Err(Error::new(format!("side {name}: class path entry {index} is not a JAR")));
            };
            entries.insert(index.to_string(), json!({ "manifest": manifest, "entries": logical }));
        }
        let mut side_answer = json!({ "bindings": bindings, "entries": entries });
        if side.qualify_stock {
            side_answer["stockQualification"] = match cp.jbmc_multi_release_gap() {
                Some(problem) => json!({"status": "unqualified", "reason": problem}),
                None => json!({"status": "ordinary class members"}),
            };
        }
        sides.insert(name.clone(), side_answer);
    }
    let home = crate::classpath::binding_java_home().map(|h| h.display().to_string());
    Ok(json!({ "schema": SCHEMA, "bound_release": bound, "java_home": home, "sides": sides }))
}

fn bind(cp: &ClassPath, asked: &Asked) -> Result<Value, Error> {
    let internal = asked.class.replace('.', "/");
    let binding = match cp.bind(&internal) {
        Ok(binding) => binding,
        Err(refusal) => return Ok(json!({ "class": refusal.class, "refused": refusal })),
    };
    let mut out = serde_json::to_value(&binding).map_err(|e| Error::new(e.to_string()))?;
    if let Some(method) = &asked.method {
        let bytes = cp.bound_bytes(&binding)?;
        let class = ClassFile::parse(&bytes).map_err(|e| Error::new(format!("{} in {}: {e}", binding.selected.entry, binding.selected.provider)))?;
        if class.name != internal {
            return Err(Error::new(format!("{} in {} is the class {}, not {}", binding.selected.entry, binding.selected.provider, class.name.replace('/', "."), binding.class)));
        }
        let overloads: Vec<&str> = class.methods_named(method).map(|m| m.descriptor.as_str()).collect();
        let found = match &asked.descriptor {
            Some(descriptor) => class.method(method, descriptor),
            None => class.methods_named(method).next().filter(|_| overloads.len() == 1),
        };
        out["method"] = json!({
            "name": method,
            "descriptor": found.map(|m| m.descriptor.clone()).or_else(|| asked.descriptor.clone()),
            "declared": found.is_some(),
            "access": found.map(|m| m.access),
            "static": found.map(|m| m.is_static()),
            "overloads": overloads,
        });
    }
    Ok(out)
}
