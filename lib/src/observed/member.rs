//! Verify the declaring file and erased signature independently of the reflection object's metadata.
use crate::classfile::MethodDescriptor;
use crate::classpath::ClassPath;
use crate::{digest::sha256_hex, Error};
use serde_json::Value;

pub(super) fn has_methods(state: &Value) -> bool {
    state["objects"].as_array().into_iter().flatten().any(|o| o["k"] == "method")
}

#[derive(Clone, Debug, PartialEq, Eq, serde::Deserialize, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MethodFact {
    pub owner: String,
    pub name: String,
    pub descriptor: String,
    pub modifiers: u16,
    pub loader: String,
    pub module: Option<String>,
    pub declaring_sha256: String,
    pub accessible_override: bool,
}

impl MethodFact {
    pub(super) fn read(raw: &Value) -> Result<Self, Error> {
        serde_json::from_value(raw.clone()).map_err(|e| Error::new(format!("incomplete observed reflective member: {e}")))
    }

    pub(super) fn bind(&self, cp: &ClassPath) -> Result<(), Error> {
        let problem = |reason: &str| Error::new(format!("observed reflective member {}#{}{}: {reason}", self.owner, self.name, self.descriptor));
        if self.accessible_override { return Err(problem("accessible override is set; capture cannot admit this access state")); }
        if self.name.starts_with('<') || MethodDescriptor::parse(&self.descriptor).is_err() { return Err(problem("invalid Method descriptor")); }
        let (bytes, module) = match self.loader.as_str() {
            "bootstrap" if crate::classpath::is_jdk_name(&self.owner) => {
                let image = cp.jdk().ok_or_else(|| problem("missing JDK image"))?;
                (image.read_class(&self.owner)?, image.module_of(&self.owner))
            }
            "application" if !crate::classpath::is_jdk_name(&self.owner) => (cp.application_bytes(&self.owner)?, None),
            _ => return Err(problem("unsupported or crossed defining loader")),
        };
        let bytes = bytes.ok_or_else(|| problem("missing declaring bytes on the original classpath"))?;
        if self.module != module || sha256_hex(&bytes) != self.declaring_sha256 { return Err(problem("module or declaring class digest differs")); }
        let cf = crate::classfile::ClassFile::parse(&bytes)?;
        let method = cf.method(&self.name, &self.descriptor).ok_or_else(|| problem("declaration absent from original class bytes"))?;
        if cf.name != self.owner || method.access != self.modifiers { return Err(problem("declaring type or modifiers differ")); }
        Ok(())
    }
}

/// Resolve each saved field back to a lookup return and the write of that same
/// reflection object, both in this VM. Distinct copies of the same member keep
/// distinct aliases. A separate JVM can compare the shape without comparing VM ids.
pub(super) fn capture(binary: &str, raw: &Value, trace: &Value, tool: &ClassPath) -> Result<Value, Error> {
    use std::collections::{BTreeMap, BTreeSet};
    if trace["schema"] != "jvm-startup-trace/v1" || trace["boundary"] != super::receipt::BOUNDARY {
        return Err(Error::new("incomplete reflective startup boundary"));
    }
    let events = trace["events"].as_array().ok_or_else(|| Error::new("missing lookup events"))?;
    let mut lookups = BTreeMap::new();
    let mut writes = BTreeMap::new();
    for event in events {
        let op = event["operation"].as_str().unwrap_or("");
        if op.starts_with("getMethod(") {
            if event.get("threw").is_some() { continue; }
            let found = &event["member"];
            let req = &event["requested"];
            let params = found["descriptor"].as_str().and_then(|s| s.strip_prefix('(')?.split_once(')')).map(|p| p.0);
            if req["class"].as_str().map(|n| n.replace('.', "/")).as_deref() != found["owner"].as_str()
                || req["name"] != found["name"] || params.is_none() || req["parameters"].as_str() != params {
                return Err(Error::new("requested member and independently observed return differ or need inherited lookup"));
            }
            let id = found["alias"].as_u64().ok_or_else(|| Error::new("missing reflective lookup identity"))?;
            lookups.insert(id, found);
        } else if op == "putstatic" {
            let field = event["field"].as_str().ok_or_else(|| Error::new("unbound reflective assignment"))?;
            writes.insert(field, &event["member"]);
        } else {
            return Err(Error::new(format!("unsupported reflective use during initialization: {op} at {}", event["stack"][1])));
        }
    }
    let root = binary.replace('.', "/");
    let states = std::iter::once((root.as_str(), raw)).chain(raw["on"]["initialized"].as_array().into_iter().flatten()
        .filter_map(|i| i["name"].as_str().map(|name| (name, i))));
    let mut fields = Vec::new();
    for (name, state) in states {
        let objects = state["objects"].as_array().ok_or_else(|| Error::new("missing separate reflective object table"))?;
        let method_ids: BTreeSet<_> = objects.iter().enumerate().filter_map(|(i, o)| (o["k"] == "method").then_some(i)).collect();
        let mut seen = BTreeMap::new();
        let mut reverse = BTreeMap::new();
        let cf = tool.application(name)?.ok_or_else(|| Error::new(format!("missing reflective field owner {name}")))?;
        for field in state["fields"].as_array().into_iter().flatten() {
            let label = field["name"].as_str().unwrap_or("");
            let full = format!("{}#{label}", name.replace('/', "."));
            let declared = cf.fields.iter().any(|f| f.is_static() && f.name == label && f.descriptor == "Ljava/lang/reflect/Method;");
            let slot = field["value"]["o"].as_u64().map(|v| v as usize);
            if !declared {
                if slot.is_some_and(|i| method_ids.contains(&i)) { return Err(Error::new(format!("untraced reflective alias in {full}"))); }
                continue;
            }
            let assigned = writes.get(full.as_str()).copied();
            if field["value"].is_null() && assigned.is_none_or(Value::is_null) {
                fields.push(serde_json::json!({"field":full,"member":null,"writeObserved":assigned.is_some()}));
                continue;
            }
            let problem = || Error::new(format!("reflective lookup, assignment, alias or declaring bytes did not bind for {full}"));
            let slot = slot.filter(|i| method_ids.contains(i)).ok_or_else(problem)?;
            let method = MethodFact::read(&objects[slot])?;
            method.bind(tool)?;
            let assigned = assigned.ok_or_else(problem)?;
            let id = assigned["alias"].as_u64().ok_or_else(problem)?;
            if lookups.get(&id).copied() != Some(assigned) || assigned["owner"] != method.owner || assigned["name"] != method.name
                || assigned["descriptor"] != method.descriptor || assigned["modifiers"] != method.modifiers
                || assigned["accessibleOverride"] != method.accessible_override
                || assigned["loader"] != (if method.loader == "bootstrap" { "bootstrap" } else { "jdk.internal.loader.ClassLoaders$AppClassLoader" })
                || seen.insert(slot, id).is_some_and(|old| old != id) || reverse.insert(id, slot).is_some_and(|old| old != slot) { return Err(problem()); }
            fields.push(serde_json::json!({"field":full,"member":method,"alias":id,"arity":MethodDescriptor::parse(&method.descriptor)?.params.len()}));
        }
        if method_ids.iter().any(|i| !seen.contains_key(i)) { return Err(Error::new("escaped reflective alias outside the traced static fields")); }
    }
    Ok(serde_json::json!({"fields":fields,"events":events}))
}

pub(super) fn publish(work: &std::path::Path, mut record: Value, complete: bool) -> Result<String, Error> {
    record["effectCoverage"] = if complete { "all transitive comparisons passed".into() } else { "reflective comparison only; not reusable".into() };
    let id = sha256_hex(record.to_string().as_bytes());
    record["id"] = id.clone().into();
    let directory = if complete { "startup-receipts" } else { "startup-diagnostics" };
    let path = super::receipt::write(&work.join(directory), &record)?;
    eprintln!("reflective startup {} {id} ({})", if complete { "receipt" } else { "comparison" }, path.display());
    Ok(id)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::classfile::{flags, writer::{ClassWriter, MethodWriter}};

    #[test]
    fn recorded_member_requires_its_exact_declaration_and_access_state() {
        let directory = tempfile::tempdir().unwrap();
        let mut class = ClassWriter::new("Target");
        class.methods.push(MethodWriter { access: flags::PUBLIC | flags::NATIVE, name: "value".into(),
            descriptor: "(Ljava/lang/String;)I".into(), code: None });
        let bytes = class.to_bytes();
        std::fs::write(directory.path().join("Target.class"), &bytes).unwrap();
        let mut cp = ClassPath::new();
        cp.add(directory.path()).unwrap();
        let valid = MethodFact { owner: "Target".into(), name: "value".into(), descriptor: "(Ljava/lang/String;)I".into(),
            modifiers: flags::PUBLIC | flags::NATIVE, loader: "application".into(), module: None,
            declaring_sha256: sha256_hex(&bytes), accessible_override: false };
        valid.bind(&cp).unwrap();
        for wrong in [MethodFact { descriptor: "()I".into(), ..valid.clone() },
            MethodFact { loader: "bootstrap".into(), ..valid.clone() }, MethodFact { accessible_override: true, ..valid.clone() },
            MethodFact { modifiers: flags::PRIVATE, ..valid.clone() }, MethodFact { declaring_sha256: "0".repeat(64), ..valid.clone() }] {
            assert!(wrong.bind(&cp).is_err());
        }
    }
}
