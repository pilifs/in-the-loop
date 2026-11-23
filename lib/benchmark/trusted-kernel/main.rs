//! Independent checker. Its only shared implementation is SHA-256.
mod bytecode;
mod classfile;
#[path = "../../src/digest.rs"]
mod digest;
mod index;
mod scalar;
mod witness;

use classfile::Class;
use digest::sha256_hex;
use std::collections::BTreeSet;
use std::{env, fs};

#[derive(Debug)]
struct Failure(&'static str, String);
type Result<T> = std::result::Result<T, Failure>;
fn reject(reason: impl Into<String>) -> Failure {
    Failure("rejected", reason.into())
}
fn unsupported(reason: impl Into<String>) -> Failure {
    Failure("unsupported", reason.into())
}

struct Request<'a> {
    theorem: &'a str,
    owner: &'a str,
    digest: &'a str,
    entry: (&'a str, &'a str),
    companion: (&'a str, &'a str),
    support: Option<(&'a str, &'a str)>,
}
fn parse_request(text: &str) -> Result<Request<'_>> {
    let rows: Vec<Vec<&str>> = text
        .lines()
        .map(|l| l.split_ascii_whitespace().collect())
        .collect();
    if !(6..=7).contains(&rows.len())
        || rows[0] != ["request", "1"]
        || rows[2] != ["environment", "initialized-verified-jvm-v1"]
    {
        return Err(unsupported("request format or environmental assumptions"));
    }
    let ["theorem", theorem] = rows[1][..] else {
        return Err(reject("missing external theorem"));
    };
    let ["class", owner, digest] = rows[3][..] else {
        return Err(reject("missing external class"));
    };
    let ["entry", name, desc] = rows[4][..] else {
        return Err(reject("missing external entry"));
    };
    let ["companion", peer, peer_desc] = rows[5][..] else {
        return Err(reject("missing companion"));
    };
    let support = match rows.get(6).map(Vec::as_slice) {
        None => None,
        Some(["support", n, h]) => Some((*n, *h)),
        _ => return Err(reject("bad support")),
    };
    Ok(Request {
        theorem,
        owner,
        digest,
        entry: (name, desc),
        companion: (peer, peer_desc),
        support,
    })
}

type Obligations = BTreeSet<String>;
fn obligation(out: &mut Obligations, method: &classfile::Code, pc: usize, edge: &str, kind: &str) {
    out.insert(format!(
        "{}{}@{}>{} {}",
        method.name, method.desc, pc, edge, kind
    ));
}
fn read(path: &str) -> Result<Vec<u8>> {
    fs::read(path).map_err(|err| reject(format!("input: {err}")))
}
fn check(args: &[String]) -> Result<String> {
    let [request_path, certificate, artifact, support @ ..] = args else {
        return Err(reject("usage: kernel REQUEST CERTIFICATE CLASS [SUPPORT]"));
    };
    let req_bytes = read(request_path)?;
    let text = std::str::from_utf8(&req_bytes).map_err(|_| reject("request encoding"))?;
    let req = parse_request(text)?;
    let raw = read(artifact)?;
    if sha256_hex(&raw) != req.digest {
        return Err(reject("external class digest"));
    }
    let class = Class::parse(&raw)?;
    if class.owner != req.owner {
        return Err(reject("defining class"));
    }
    match (req.support, support) {
        (Some((name, h)), [path]) => {
            let parent = read(path)?;
            if name != class.parent
                || sha256_hex(&parent) != h
                || Class::parse(&parent)?.owner != name
            {
                return Err(reject("support class binding"));
            }
        }
        (None, []) if class.parent == "java/lang/Object" => (),
        _ => return Err(reject("superclass resolution")),
    }
    let evidence = read(certificate)?;
    let evidence = std::str::from_utf8(&evidence).map_err(|_| reject("certificate encoding"))?;
    let mut lines = evidence.lines();
    if lines.next() != Some("certificate 1")
        || lines.next() != Some(&format!("request {}", sha256_hex(&req_bytes)))
    {
        return Err(reject("certificate does not bind external request"));
    }
    let hints = lines.next().ok_or_else(|| reject("missing hints"))?;
    let mut actual = Obligations::new();
    for key in lines {
        if !actual.insert(key.to_owned()) {
            return Err(reject("duplicate obligation"));
        }
    }
    let mut needed = Obligations::new();
    match req.theorem {
        "scalar-equality-v1" => scalar::check(&class, &req, hints, &mut needed)?,
        "least-index-frame-total-v1" => index::check(&class, &req, hints, &mut needed)?,
        _ => return Err(unsupported("external theorem")),
    }
    if let Some(key) = needed.difference(&actual).next() {
        return Err(reject(format!("missing obligation {key}")));
    }
    if let Some(key) = actual.difference(&needed).next() {
        return Err(reject(format!("unexpected obligation {key}")));
    }
    Ok(format!("accepted {} {}#{}{} companion {}{} environment initialized-verified-jvm-v1 class {} request {} obligations {}",
        req.theorem,req.owner,req.entry.0,req.entry.1,req.companion.0,req.companion.1,req.digest,sha256_hex(&req_bytes),needed.len()))
}
fn main() {
    match check(&env::args().skip(1).collect::<Vec<_>>()) {
        Ok(line) => println!("{line}"),
        Err(Failure(tag, reason)) => {
            println!("{tag} {reason}");
            std::process::exit(if tag == "unsupported" { 3 } else { 2 });
        }
    }
}
