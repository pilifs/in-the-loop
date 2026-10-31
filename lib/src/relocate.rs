//! Copies a directory of compiled classes into a new package prefix, so that two versions of the same classes can
//! be loaded side by side: `net/example/Pricing` becomes `before/net/example/Pricing`, and every reference between
//! the copied classes follows.
//!
//! Class names only ever appear in a class file's constant pool, as UTF-8 entries: on their own (class entries),
//! inside field and method descriptors (`Lnet/example/Pricing;`), and inside generic signatures
//! (`Lnet/example/Pricing<...>;`). Rewriting those entries, and nothing else, relocates the class. Everything after
//! the constant pool refers to entries by index and is copied unchanged.

use std::collections::BTreeSet;
use std::path::Path;

use crate::classfile::{decode_modified_utf8, encode_modified_utf8};
use crate::Error;

/// Copies every class under `input` to `output/<prefix>/...`, renamed. Returns the relocated class names.
pub fn directory(input: &Path, output: &Path, prefix: &str) -> Result<BTreeSet<String>, Error> {
    let mut files = Vec::new();
    collect(input, input, &mut files)?;
    let own: BTreeSet<String> = files.iter().map(|(name, _)| name.clone()).collect();
    for (name, path) in &files {
        let target = output.join(prefix).join(format!("{name}.class"));
        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let bytes = std::fs::read(path)?;
        std::fs::write(&target, class_file(&bytes, &own, prefix)?)?;
    }
    Ok(own)
}

fn collect(root: &Path, dir: &Path, out: &mut Vec<(String, std::path::PathBuf)>) -> Result<(), Error> {
    for entry in std::fs::read_dir(dir)? {
        let path = entry?.path();
        if path.is_dir() {
            collect(root, &path, out)?;
        } else if path.extension().is_some_and(|e| e == "class") {
            let relative = path.strip_prefix(root).unwrap_or(&path).with_extension("");
            out.push((relative.to_string_lossy().replace('\\', "/"), path));
        }
    }
    Ok(())
}

/// Rewrites one class file's constant pool.
pub fn class_file(bytes: &[u8], own: &BTreeSet<String>, prefix: &str) -> Result<Vec<u8>, Error> {
    let mut out = Vec::with_capacity(bytes.len() + 256);
    let mut pos = 0usize;
    let mut take = |n: usize| -> Result<&[u8], Error> {
        let slice = bytes.get(pos..pos + n).ok_or_else(|| Error::new("truncated class file"))?;
        pos += n;
        Ok(slice)
    };
    out.extend_from_slice(take(8)?); // magic, minor, major
    let count_bytes = take(2)?;
    let count = u16::from_be_bytes([count_bytes[0], count_bytes[1]]);
    out.extend_from_slice(count_bytes);
    let mut i = 1;
    while i < count {
        let tag = take(1)?[0];
        out.push(tag);
        match tag {
            1 => {
                let len_bytes = take(2)?;
                let len = u16::from_be_bytes([len_bytes[0], len_bytes[1]]) as usize;
                let text = decode_modified_utf8(take(len)?);
                let renamed = encode_modified_utf8(&rename(&text, own, prefix));
                out.extend((renamed.len() as u16).to_be_bytes());
                out.extend(renamed);
            }
            3 | 4 => out.extend_from_slice(take(4)?),
            5 | 6 => {
                out.extend_from_slice(take(8)?);
                i += 1;
            }
            7 | 8 | 16 | 19 | 20 => out.extend_from_slice(take(2)?),
            9 | 10 | 11 | 12 | 17 | 18 => out.extend_from_slice(take(4)?),
            15 => out.extend_from_slice(take(3)?),
            other => return Err(Error::new(format!("unknown constant pool tag {other}"))),
        }
        i += 1;
    }
    out.extend_from_slice(&bytes[pos..]);
    Ok(out)
}

/// Renames a constant pool string if it is a relocated class name or contains one as a descriptor.
pub fn rename(s: &str, own: &BTreeSet<String>, prefix: &str) -> String {
    if own.contains(s) {
        return format!("{prefix}/{s}");
    }
    if !s.contains('L') {
        return s.to_string();
    }
    let chars: Vec<char> = s.chars().collect();
    let mut result = String::with_capacity(s.len() + 16);
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == 'L' {
            let mut end = i + 1;
            while end < chars.len() && chars[end] != ';' && chars[end] != '<' {
                end += 1;
            }
            let name: String = chars[i + 1..end].iter().collect();
            if own.contains(&name) {
                result.push('L');
                result.push_str(prefix);
                result.push('/');
                result.push_str(&name);
                i = end;
                continue;
            }
        }
        result.push(chars[i]);
        i += 1;
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renames_names_and_descriptors() {
        let own: BTreeSet<String> = ["a/B".to_string()].into_iter().collect();
        assert_eq!(rename("La/B;", &own, "before"), "Lbefore/a/B;");
        assert_eq!(rename("(JLa/B<La/C;>;)V", &own, "before"), "(JLbefore/a/B<La/C;>;)V");
        assert_eq!(rename("a/B", &own, "before"), "before/a/B");
        assert_eq!(rename("a/BC", &own, "before"), "a/BC");
        assert_eq!(rename("hello", &own, "before"), "hello");
    }
}
