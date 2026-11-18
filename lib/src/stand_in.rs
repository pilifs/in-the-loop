//! Stand-ins for library methods, sampled on a JVM (`prove --stand-in CLASS`).
//!
//! Some library code is out of the own checker's reach for a reason that has nothing to do with the claim:
//! reflection, introspection caches, the JDK's `java.beans`. Spring's `BeanWrapperImpl` resolves a property name
//! through `CachedIntrospectionResults` and calls the setter with `Method.invoke`, and every path of
//! `DataBinder.bind` goes through it (example 286). A stand-in is a class, compiled against the check's class path,
//! that says what such a method does for the receivers it covers, in plain bytecode the checker runs:
//!
//! - each `public static` method of it but `main` stands in for an instance method: its first parameter's class `T`
//!   is the exact class of the receivers it covers, and the rest of its descriptor is the method's, which `T`
//!   declares or inherits. A call that resolves to that method on a receiver of exactly `T` runs the stand-in
//!   instead ([`crate::bmc::StandIn`]); a receiver of a subclass, or a call the stand-in makes itself, runs the
//!   method as written. So a stand-in hands what it does not cover back to the method by calling it;
//! - its `public static void main(String[])` samples it against the method on a JVM: one line per sample,
//!   `sample<TAB>input<TAB>the method's outcome<TAB>the stand-in's outcome`, each outcome what the sampler compares
//!   (the receiver's state, the arguments', the exception's class) written as text.
//!
//! Before the run the tool runs that `main` on the check's class path, as it is ([`prepare`]), and takes the
//! stand-in only where it printed at least one sample and the two outcomes are the same text on every sample. A
//! result that made such a call states that it rests on it: sampling is evidence, not a proof, and what a sampler
//! does not compare is not checked at all. A refutation through a stand-in is still replayed on a JVM, where the
//! method runs as written.

use crate::bmc::StandIn;
use crate::classfile::{flags, ClassFile};
use crate::Error;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant};

/// How long a sampler may run.
const TIMEOUT: Duration = Duration::from_secs(120);

/// The stand-ins of `classes` (binary or internal names) on `classpath`, each sampled on a JVM, with the working
/// files under `work`. An error where a class is not on the class path, a public static method of it stands in for
/// no instance method, it has no `main`, or its sampler fails, samples nothing or finds a difference.
pub fn prepare(classes: &[String], classpath: &[PathBuf], work: &Path) -> Result<Vec<StandIn>, Error> {
    let mut out = Vec::new();
    if classes.is_empty() {
        return Ok(out);
    }
    let mut tool = crate::classpath::ClassPath::new();
    for entry in classpath {
        tool.add(entry)?;
    }
    let dir = work.join("stand-in");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir)?;
    for class in classes {
        let internal = class.replace('.', "/");
        let binary = internal.replace('/', ".");
        let bytes = tool.application_bytes(&internal)?.ok_or_else(|| Error::new(format!("--stand-in {binary}: the check's class path has no such class")))?;
        let cf = ClassFile::parse(&bytes).map_err(|e| Error::new(format!("--stand-in {binary}: its class file does not parse: {e}")))?;
        let replaced = replacements(&tool, &cf)?;
        if replaced.is_empty() {
            return Err(Error::new(format!("--stand-in {binary}: it has no public static method that stands in for one (its first parameter the receiver's class, the rest the method's descriptor)")));
        }
        if !cf.methods.iter().any(|m| m.name == "main" && m.descriptor == "([Ljava/lang/String;)V" && m.is_static() && m.access & flags::PUBLIC != 0) {
            return Err(Error::new(format!("--stand-in {binary}: it has no main to sample it against the method it stands in for")));
        }
        let samples = sample(&binary, classpath, &dir)?;
        for (owner, name, descriptor, receiver, method_descriptor) in replaced {
            let assumption = format!(
                "{binary}.{name} stands in for {}.{name}{descriptor} on a receiver of exactly {} (--stand-in): its main sampled it against the method on a JVM on this class path, {} sample{}, the two the same on each in what the sampler compares (sha256 {} of what it printed), and not proved",
                owner.replace('/', "."),
                receiver.replace('/', "."),
                samples.count,
                if samples.count == 1 { "" } else { "s" },
                &samples.sha256[..16],
            );
            out.push(StandIn { owner, name: name.clone(), descriptor, receiver, class: internal.clone(), method: name, method_descriptor, assumption });
        }
    }
    Ok(out)
}

/// The methods a stand-in class's public static methods stand in for, but `main`: (the class that declares the
/// method, its name, its descriptor, the receiver's exact class, the stand-in's descriptor).
fn replacements(tool: &crate::classpath::ClassPath, cf: &ClassFile) -> Result<Vec<(String, String, String, String, String)>, Error> {
    let binary = cf.name.replace('/', ".");
    let mut out = Vec::new();
    for m in cf.methods.iter().filter(|m| m.is_static() && m.access & flags::PUBLIC != 0 && m.name != "main" && m.name != "<clinit>") {
        let Some((receiver, descriptor)) = without_receiver(&m.descriptor) else {
            return Err(Error::new(format!("--stand-in {binary}: its public static method {}{} has no receiver: its first parameter is the class of the receivers it stands in for (a helper is not public)", m.name, m.descriptor)));
        };
        let Some((declaring, method)) = tool.checker_method(&receiver, &m.name, &descriptor) else {
            return Err(Error::new(format!("--stand-in {binary}: its public static method {}{} stands in for no method: {} neither declares nor inherits {}{descriptor} (a helper is not public)", m.name, m.descriptor, receiver.replace('/', "."), m.name)));
        };
        if method.is_static() || method.code.is_none() {
            return Err(Error::new(format!("--stand-in {binary}: {}.{}{descriptor} is static or has no code, so no call on a receiver runs it", declaring.name.replace('/', "."), m.name)));
        }
        if !tool.is_application(&declaring.name) {
            return Err(Error::new(format!("--stand-in {binary}: {}.{}{descriptor} is the JDK's: a stand-in is for a method of the check's class path", declaring.name.replace('/', "."), m.name)));
        }
        out.push((declaring.name.clone(), m.name.clone(), descriptor, receiver, m.descriptor.clone()));
    }
    Ok(out)
}

/// A static method's descriptor without its first parameter, a class: (that class, the rest).
fn without_receiver(descriptor: &str) -> Option<(String, String)> {
    let rest = descriptor.strip_prefix("(L")?;
    let end = rest.find(';')?;
    Some((rest[..end].to_string(), format!("({}", &rest[end + 1..])))
}

/// What a sampler printed: how many samples, and the sha256 of its lines.
struct Samples {
    count: usize,
    sha256: String,
}

/// Runs the stand-in's `main` on the class path and reads its samples.
fn sample(binary: &str, classpath: &[PathBuf], dir: &Path) -> Result<Samples, Error> {
    let home = crate::jimage::JImage::find_java_home().ok_or_else(|| Error::new("--stand-in: no JDK to sample a stand-in on (set JAVA_HOME)"))?;
    let absolute = |p: &Path| std::path::absolute(p).unwrap_or_else(|_| p.to_path_buf());
    let class_path = std::env::join_paths(classpath.iter().map(|e| absolute(e))).map_err(|e| Error::new(format!("a class path entry cannot be joined: {e}")))?;
    let stdout = dir.join(format!("{binary}.stdout"));
    let stderr = dir.join(format!("{binary}.stderr"));
    let mut child = Command::new(home.join("bin").join("java"))
        .args(["-Xmx256m", "-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1", "-XX:-UsePerfData", "-cp"])
        .arg(&class_path)
        .arg(binary)
        .current_dir(dir)
        .stdout(std::fs::File::create(&stdout)?)
        .stderr(std::fs::File::create(&stderr)?)
        .spawn()
        .map_err(|e| Error::new(format!("cannot run the JVM: {e}")))?;
    let started = Instant::now();
    let status = loop {
        if let Some(status) = child.try_wait()? {
            break status;
        }
        if started.elapsed() > TIMEOUT {
            let _ = child.kill();
            let _ = child.wait();
            return Err(Error::new(format!("--stand-in {binary}: its sampler did not finish within {} s", TIMEOUT.as_secs())));
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    let text = std::fs::read_to_string(&stdout).unwrap_or_default();
    if !status.success() {
        let said = std::fs::read_to_string(&stderr).unwrap_or_default();
        let tail: Vec<&str> = said.lines().rev().take(3).collect();
        return Err(Error::new(format!("--stand-in {binary}: its sampler failed ({status}){}", if tail.is_empty() { String::new() } else { format!(": {}", tail.into_iter().rev().collect::<Vec<_>>().join(" / ")) })));
    }
    let lines: Vec<&str> = text.lines().filter(|l| l.starts_with("sample\t")).collect();
    for line in &lines {
        let parts: Vec<&str> = line.split('\t').collect();
        let [_, input, method, stand_in] = parts.as_slice() else {
            return Err(Error::new(format!("--stand-in {binary}: a sample is not `sample<TAB>input<TAB>the method's outcome<TAB>the stand-in's outcome`: {line}")));
        };
        if method != stand_in {
            return Err(Error::new(format!("--stand-in {binary}: on {input} the method gives {method} and the stand-in {stand_in}, so the check cannot take it")));
        }
    }
    if lines.is_empty() {
        return Err(Error::new(format!("--stand-in {binary}: its sampler printed no sample, so nothing shows it does what the method does")));
    }
    Ok(Samples { count: lines.len(), sha256: crate::digest::sha256_hex(lines.join("\n").as_bytes()) })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_stand_ins_descriptor_loses_its_receiver() {
        assert_eq!(without_receiver("(Lorg/x/A;Lorg/x/V;)V"), Some(("org/x/A".to_string(), "(Lorg/x/V;)V".to_string())));
        assert_eq!(without_receiver("(Lorg/x/A;)I"), Some(("org/x/A".to_string(), "()I".to_string())));
        assert_eq!(without_receiver("(ILorg/x/A;)V"), None);
        assert_eq!(without_receiver("([Lorg/x/A;)V"), None);
    }
}
