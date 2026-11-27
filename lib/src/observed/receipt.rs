//! Deployment bindings and atomic publication shared by typed startup recordings.
use super::{Jvm, Runtime};
use crate::classpath::ClassPath;
use crate::digest::{sha256_hex, sha256_reader};
use crate::Error;
use serde_json::{json, Value};
use std::fs::File;
use std::io::Write;
use std::path::{Path, PathBuf};

pub(super) const TRACER: &str = include_str!("StartupTrace.java");
pub(super) const BOUNDARY: &str = "ObservedInitializer#initializeRoots([Ljava/lang/String;Ljava/lang/ClassLoader;ZI)Ljava/lang/Class;";
pub(super) fn read_json(path: &Path) -> Result<Value, Error> {
    serde_json::from_reader(File::open(path)?).map_err(|e| Error::new(format!("{}: {e}", path.display())))
}

pub(super) fn bindings(tool: &ClassPath, home: &Path, entries: &[PathBuf], roots: &[String], runtime: &Runtime) -> Result<Value, Error> {
    let mut artifacts = Vec::new();
    for path in entries {
        let digest = if path.is_dir() { crate::classpath::lookup_directory(path, &mut Vec::new())? }
            else { sha256_reader(File::open(path)?)? };
        artifacts.push(json!({"path":path,"origin": path.canonicalize()?, "sha256": digest}));
    }
    let image = tool.jdk().ok_or_else(|| Error::new("startup receipt requires a JDK image"))?;
    let mut classes = serde_json::Map::new();
    let required = if runtime.record_joint_startup { ["java/lang/Class", "java/lang/System", "java/lang/Thread", "java/lang/ClassLoader"] }
        else if runtime.live_properties { ["java/util/Properties", "java/lang/System", "java/util/Hashtable", "java/util/concurrent/ConcurrentHashMap"] }
        else if runtime.reflective_members { ["java/lang/Class", "java/lang/reflect/Method", "java/lang/reflect/AccessibleObject", "java/lang/reflect/Executable"] }
        else { ["java/lang/String", "java/nio/charset/Charset", "sun/nio/cs/UTF_8", "sun/nio/cs/US_ASCII"] };
    for class in required {
        let bytes = image.read_class(class)?.ok_or_else(|| Error::new(format!("missing JDK charset class {class}")))?;
        classes.insert(class.into(), sha256_hex(&bytes).into());
    }
    let mut request = runtime.clone();
    request.expected_charset_receipt = None;
    request.expected_charset_name = None;
    request.charset_receipt_directory = None;
    let supplied = if request.startup_properties.is_empty() { None } else { Some(sha256_hex(json!(request.startup_properties).to_string().as_bytes())) };
    request.startup_properties.clear();
    Ok(json!({"orderedArtifacts":artifacts, "orderedRoots":roots, "loader":"system application loader, parent delegation",
        "jdkHome":home.canonicalize()?, "jdkReleaseSha256":sha256_reader(File::open(home.join("release"))?)?,
        "jdkModulesSha256":sha256_reader(File::open(home.join("lib/modules"))?)?, "jdkClasses":classes,
        "javaSha256":sha256_reader(File::open(home.join("bin/java"))?)?, "vmSha256":sha256_reader(File::open(home.join("lib/server/libjvm.so"))?)?,
        "observerSha256":sha256_hex(super::SOURCE.as_bytes()), "tracerSha256":sha256_hex(TRACER.as_bytes()),
        "rulesSha256": if runtime.record_joint_startup { sha256_hex(include_bytes!("../observed.rs")) } else if runtime.live_properties { sha256_hex(include_bytes!("table.rs")) } else if runtime.reflective_members { sha256_hex(include_bytes!("member.rs")) } else { sha256_hex(include_bytes!("charset.rs")) },
        "tableRecorderSha256":runtime.live_properties.then(||sha256_hex(super::table::SOURCE.as_bytes())), "startupPropertiesSha256":supplied,
        "bindingRulesSha256":sha256_hex(include_bytes!("receipt.rs")), "runtime":request,
        "fileEncodingOption":runtime.charset_locale.map(|_| "COMPAT"),
        "boundary":BOUNDARY}))
}

pub(super) fn trace(jvm: &Jvm, binary: &str, suffix: &str) -> Result<Value, Error> {
    let data = read_json(&jvm.dir.join(format!("{binary}{suffix}.trace.json")))?;
    if data["schema"] != "jvm-startup-trace/v1" || data["boundary"] != BOUNDARY || !data["events"].is_array() {
        return Err(Error::new("incomplete JVM charset recording"));
    }
    Ok(data)
}

pub(super) fn write(dir: &Path, receipt: &Value) -> Result<PathBuf, Error> {
    std::fs::create_dir_all(&dir)?;
    let path = dir.join(format!("{}.json", receipt["id"].as_str().unwrap()));
    let mut file = tempfile::NamedTempFile::new_in(dir)?;
    serde_json::to_writer_pretty(file.as_file_mut(), receipt).map_err(|e| Error::new(e.to_string()))?;
    file.write_all(b"\n")?;
    file.as_file().sync_all()?;
    file.persist(&path).map_err(|e| Error::from(e.error))?;
    Ok(path)
}
