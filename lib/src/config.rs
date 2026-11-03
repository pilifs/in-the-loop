//! The configuration keys of a Spring Boot module, cross-checked three ways: the keys its classes read (`${...}`
//! placeholders in annotations, `@ConfigurationProperties` fields, `@ConditionalOnProperty`,
//! `Environment.getProperty` with a constant), the keys its `application*.yaml|yml|properties` files set, and the
//! keys the class path's configuration metadata (`META-INF/spring-configuration-metadata.json`, which every Spring
//! Boot starter and every module built with the configuration processor carries) declares. The result is the
//! `configuration` block of the boundary contract: one line per key with its type and the value each file gives it,
//! who reads it under it, and a `!` line where a file sets a key that nothing binds, a key Boot has deprecated, or a
//! value that is not of the key's type. Boot binds names relaxed (`max-seats`, `maxSeats`, `max_seats` are one
//! key), so every key is compared in its canonical form.
//!
//! The YAML reader covers what application files use: block mappings and sequences, plain and quoted scalars, flow
//! sequences, block scalars, comments and `---` documents with `spring.config.activate.on-profile`. Anchors, tags
//! and flow mappings are read as text.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

use crate::boundaries::{Bean, Member};
use crate::classfile::{flags, signature, Annotation, ClassFile, Constant, ElementValue, Field, Insn, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::wire;
use crate::Error;

/// The metadata files a class path entry may carry.
const METADATA: &[&str] = &["META-INF/spring-configuration-metadata.json", "META-INF/additional-spring-configuration-metadata.json"];
/// The keys a profile document names itself by; they are not listed.
const PROFILE_KEYS: &[&str] = &["spring.config.activate.on-profile", "spring.profiles"];

/// How a key is bound: one value, a list (`key[0]`, `key[1]` or a comma-separated scalar) or a map of further keys.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Shape {
    Exact,
    List,
    Map,
}

/// A key set in an application file, with the value as written.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Setting {
    /// Canonical: lower case, kebab case, index and map segments in brackets.
    pub key: String,
    pub value: String,
    pub file: PathBuf,
    /// `application.yaml`, `config/application-prod.properties`: the file as the contract names it.
    pub display: String,
    /// From the file name (`application-prod.yaml`) or the document's `spring.config.activate.on-profile`.
    pub profile: Option<String>,
    pub line: usize,
}

/// A key some class reads.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Binding {
    pub key: String,
    pub shape: Shape,
    /// The type the value binds to, with simple names (`int`, `Duration`, `List<String>`).
    pub ty: Option<String>,
    /// The internal name of the type when it is a class, for enum constants.
    pub ty_class: Option<String>,
    /// The placeholder's default (`${key:default}`) or the call's.
    pub default: Option<String>,
    /// `@Value in Orders.holdPolicy(int, Duration)`, `@ConfigurationProperties("holds") HoldSettings.maxSeats`.
    pub site: String,
    /// The class (internal name) the binding is in, and the line.
    pub class: String,
    pub line: Option<u16>,
}

/// A key the class path's configuration metadata declares.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Declared {
    pub shape: Shape,
    pub ty: Option<String>,
    pub source: Option<String>,
    pub deprecation: Option<Deprecation>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Deprecation {
    pub level: String,
    pub replacement: Option<String>,
    pub since: Option<String>,
    pub reason: Option<String>,
}

impl Default for Shape {
    fn default() -> Self {
        Shape::Exact
    }
}

// ---------------------------------------------------------------------------------------------------------------
// Canonical names

/// Boot's canonical form of a key: lower case, words joined by `-`, bracketed segments kept as written.
pub fn canonical(key: &str) -> String {
    let mut out = String::new();
    let mut depth = 0usize;
    let mut previous: Option<char> = None;
    for c in key.chars() {
        match c {
            '[' => {
                depth += 1;
                out.push(c);
            }
            ']' => {
                depth = depth.saturating_sub(1);
                out.push(c);
            }
            _ if depth > 0 => out.push(c),
            '_' => out.push('-'),
            c if c.is_ascii_uppercase() => {
                if previous.is_some_and(|p| p.is_ascii_lowercase() || p.is_ascii_digit()) {
                    out.push('-');
                }
                out.push(c.to_ascii_lowercase());
            }
            c => out.push(c),
        }
        previous = Some(c);
    }
    out
}

/// `key[3]` → `key`, `map[the.entry]` → `map`: the key without its last bracketed segment, if it has one.
fn without_index(key: &str) -> Option<&str> {
    if key.ends_with(']') {
        key.rfind('[').map(|i| &key[..i])
    } else {
        None
    }
}

/// The parent of `a.b.c` is `a.b`; of `a.b[0]` is `a.b`.
fn parent(key: &str) -> Option<&str> {
    if let Some(base) = without_index(key) {
        return Some(base);
    }
    key.rfind('.').map(|i| &key[..i])
}

// ---------------------------------------------------------------------------------------------------------------
// Application files

/// The application files under the resource directories (`application.yaml`, `application-prod.properties`, the
/// same under `config/`), as the contract names them, and every key they set.
pub fn read_files(dirs: &[PathBuf]) -> Result<(Vec<String>, Vec<Setting>), Error> {
    let mut files = Vec::new();
    let mut settings = Vec::new();
    for dir in dirs {
        for sub in ["", "config"] {
            let folder = if sub.is_empty() { dir.clone() } else { dir.join(sub) };
            let Ok(entries) = std::fs::read_dir(&folder) else { continue };
            let mut names: Vec<String> = entries.filter_map(|e| e.ok()).map(|e| e.file_name().to_string_lossy().into_owned()).collect();
            names.sort();
            for name in names {
                let Some((stem, ext)) = name.rsplit_once('.') else { continue };
                if !matches!(ext, "yaml" | "yml" | "properties") {
                    continue;
                }
                let profile = if stem == "application" {
                    None
                } else if let Some(p) = stem.strip_prefix("application-") {
                    Some(p.to_string())
                } else {
                    continue;
                };
                let path = folder.join(&name);
                let display = if sub.is_empty() { name.clone() } else { format!("{sub}/{name}") };
                let text = std::fs::read_to_string(&path).map_err(|e| Error::new(format!("cannot read {}: {e}", path.display())))?;
                let documents = if ext == "properties" { properties(&text) } else { yaml(&text) };
                for (document_profile, keys) in documents {
                    let profile = document_profile.or_else(|| profile.clone());
                    for (key, value, line) in keys {
                        let key = canonical(&key);
                        if PROFILE_KEYS.contains(&key.as_str()) {
                            continue;
                        }
                        settings.push(Setting { key, value, file: path.clone(), display: display.clone(), profile: profile.clone(), line });
                    }
                }
                files.push(display);
            }
        }
    }
    Ok((files, settings))
}

/// The documents of a file: each one's profile, if it names one, and its `(key, value, line)` leaves.
type Documents = Vec<(Option<String>, Vec<(String, String, usize)>)>;

fn profile_of(keys: &[(String, String, usize)]) -> Option<String> {
    keys.iter().find(|(k, _, _)| PROFILE_KEYS.contains(&canonical(k).as_str())).map(|(_, v, _)| v.clone())
}

fn properties(text: &str) -> Documents {
    let mut documents: Documents = Vec::new();
    let mut keys: Vec<(String, String, usize)> = Vec::new();
    let mut pending = String::new();
    let mut start = 0;
    for (i, raw) in text.lines().enumerate() {
        let line = if pending.is_empty() { raw.trim_start() } else { raw.trim_start() };
        if pending.is_empty() {
            start = i + 1;
            if line.is_empty() {
                continue;
            }
            if line == "#---" || line == "!---" {
                documents.push((profile_of(&keys), std::mem::take(&mut keys)));
                continue;
            }
            if line.starts_with('#') || line.starts_with('!') {
                continue;
            }
        }
        if let Some(rest) = line.strip_suffix('\\') {
            pending.push_str(rest);
            continue;
        }
        pending.push_str(line);
        let entry = std::mem::take(&mut pending);
        let mut key = String::new();
        let mut chars = entry.chars().peekable();
        let mut escaped = false;
        let mut value: Option<String> = None;
        while let Some(c) = chars.next() {
            if escaped {
                key.push(c);
                escaped = false;
            } else if c == '\\' {
                escaped = true;
            } else if c == '=' || c == ':' || c.is_whitespace() {
                let mut rest: String = chars.collect();
                rest = rest.trim_start().to_string();
                if c.is_whitespace() {
                    if let Some(r) = rest.strip_prefix(['=', ':']) {
                        rest = r.trim_start().to_string();
                    }
                }
                value = Some(unescape_properties(&rest));
                break;
            } else {
                key.push(c);
            }
        }
        keys.push((key, value.unwrap_or_default(), start));
    }
    documents.push((profile_of(&keys), keys));
    documents
}

fn unescape_properties(s: &str) -> String {
    let mut out = String::new();
    let mut chars = s.chars();
    while let Some(c) = chars.next() {
        if c == '\\' {
            match chars.next() {
                Some('n') => out.push('\n'),
                Some('t') => out.push('\t'),
                Some('r') => out.push('\r'),
                Some(other) => out.push(other),
                None => {}
            }
        } else {
            out.push(c);
        }
    }
    out
}

#[derive(Debug, Clone)]
struct Line {
    indent: usize,
    /// Without its comment, trimmed.
    text: String,
    /// As in the file, for block scalars.
    raw: String,
    number: usize,
}

/// The text up to a `#` that starts a comment: one at the start or after a space, outside quotes.
fn strip_comment(s: &str) -> &str {
    let mut quote: Option<char> = None;
    let mut previous = ' ';
    for (i, c) in s.char_indices() {
        match quote {
            Some(q) if c == q => quote = None,
            Some(_) => {}
            None if c == '"' || c == '\'' => {
                if previous.is_whitespace() || previous == ':' || previous == '-' || previous == '[' || previous == ',' || i == 0 {
                    quote = Some(c);
                }
            }
            None if c == '#' && (i == 0 || previous.is_whitespace()) => return s[..i].trim_end(),
            None => {}
        }
        previous = c;
    }
    s.trim_end()
}

fn yaml(text: &str) -> Documents {
    let mut documents: Documents = Vec::new();
    let mut lines: Vec<Line> = Vec::new();
    let flush = |lines: &mut Vec<Line>, documents: &mut Documents| {
        let mut parser = Yaml { lines: std::mem::take(lines), pos: 0, out: Vec::new() };
        parser.block("");
        documents.push((profile_of(&parser.out), parser.out));
    };
    for (i, raw) in text.lines().enumerate() {
        let trimmed = raw.trim_end();
        if trimmed == "---" || trimmed.starts_with("--- ") || trimmed.starts_with("---\t") {
            flush(&mut lines, &mut documents);
            continue;
        }
        if trimmed == "..." {
            continue;
        }
        let stripped = strip_comment(raw);
        let indent = raw.len() - raw.trim_start_matches(' ').len();
        let text = stripped.trim_start().to_string();
        if text.is_empty() && !raw.trim().is_empty() && !raw.trim_start().starts_with('#') {
            continue;
        }
        if text.is_empty() {
            // Blank lines and comments matter only inside block scalars, which read the raw lines.
            lines.push(Line { indent: usize::MAX, text, raw: raw.to_string(), number: i + 1 });
            continue;
        }
        lines.push(Line { indent, text, raw: raw.to_string(), number: i + 1 });
    }
    flush(&mut lines, &mut documents);
    documents
}

struct Yaml {
    lines: Vec<Line>,
    pos: usize,
    out: Vec<(String, String, usize)>,
}

fn join_key(path: &str, key: &str) -> String {
    if path.is_empty() {
        key.to_string()
    } else if key.starts_with('[') {
        format!("{path}{key}")
    } else {
        format!("{path}.{key}")
    }
}

/// A line's key and value when it is a mapping entry: `key: value`, `key:`, `"quoted key": value`.
fn split_entry(text: &str) -> Option<(String, String)> {
    if let Some(q) = text.chars().next().filter(|c| *c == '"' || *c == '\'') {
        let (key, rest) = quoted(text, q)?;
        let rest = rest.trim_start();
        let rest = rest.strip_prefix(':')?;
        if !(rest.is_empty() || rest.starts_with(' ') || rest.starts_with('\t')) {
            return None;
        }
        return Some((key, rest.trim().to_string()));
    }
    if let Some(i) = text.find(": ") {
        return Some((text[..i].trim().to_string(), text[i + 2..].trim().to_string()));
    }
    if let Some(key) = text.strip_suffix(':') {
        return Some((key.trim().to_string(), String::new()));
    }
    None
}

/// The content of a quoted scalar that starts the text, and what follows the closing quote.
fn quoted(text: &str, q: char) -> Option<(String, &str)> {
    let mut out = String::new();
    let mut chars = text.char_indices().skip(1).peekable();
    while let Some((i, c)) = chars.next() {
        if c == q {
            if q == '\'' && chars.peek().is_some_and(|(_, n)| *n == '\'') {
                chars.next();
                out.push('\'');
                continue;
            }
            return Some((out, &text[i + c.len_utf8()..]));
        }
        if c == '\\' && q == '"' {
            match chars.next() {
                Some((_, 'n')) => out.push('\n'),
                Some((_, 't')) => out.push('\t'),
                Some((_, other)) => out.push(other),
                None => {}
            }
            continue;
        }
        out.push(c);
    }
    None
}

/// A scalar as Boot sees it: unquoted, untagged. `None` for null.
fn scalar(text: &str) -> Option<String> {
    let text = text.trim();
    let text = if text.starts_with('!') { text.split_once(' ').map(|(_, r)| r.trim()).unwrap_or("") } else { text };
    if let Some(q) = text.chars().next().filter(|c| *c == '"' || *c == '\'') {
        return quoted(text, q).map(|(s, _)| s);
    }
    if text.is_empty() || text == "~" || text == "null" {
        return None;
    }
    Some(text.to_string())
}

fn is_dash(text: &str) -> bool {
    text == "-" || text.starts_with("- ")
}

impl Yaml {
    fn next_content(&self) -> Option<&Line> {
        self.lines[self.pos..].iter().find(|l| l.indent != usize::MAX)
    }

    fn skip_blank(&mut self) {
        while self.pos < self.lines.len() && self.lines[self.pos].indent == usize::MAX {
            self.pos += 1;
        }
    }

    fn block(&mut self, path: &str) {
        self.skip_blank();
        let Some(first) = self.next_content() else { return };
        let indent = first.indent;
        if is_dash(&first.text) {
            self.sequence(path, indent);
        } else {
            self.mapping(path, indent);
        }
    }

    fn mapping(&mut self, path: &str, indent: usize) {
        loop {
            self.skip_blank();
            if self.pos >= self.lines.len() || self.lines[self.pos].indent != indent || is_dash(&self.lines[self.pos].text) {
                return;
            }
            let line = self.lines[self.pos].clone();
            let Some((key, value)) = split_entry(&line.text) else {
                self.pos += 1;
                continue;
            };
            let child = join_key(path, &key);
            self.pos += 1;
            self.value(&child, &value, indent, line.number);
        }
    }

    fn sequence(&mut self, path: &str, indent: usize) {
        let mut index = 0;
        loop {
            self.skip_blank();
            if self.pos >= self.lines.len() || self.lines[self.pos].indent != indent || !is_dash(&self.lines[self.pos].text) {
                return;
            }
            let line = self.lines[self.pos].clone();
            let item = format!("{path}[{index}]");
            index += 1;
            let rest = line.text[1..].trim_start().to_string();
            if rest.is_empty() {
                self.pos += 1;
                if self.next_content().is_some_and(|n| n.indent > indent) {
                    self.block(&item);
                }
            } else if is_dash(&rest) || split_entry(&rest).is_some() {
                let offset = line.text.len() - rest.len();
                self.lines[self.pos] = Line { indent: indent + offset, text: rest, raw: line.raw, number: line.number };
                self.block(&item);
            } else {
                if let Some(v) = scalar(&rest) {
                    self.out.push((item, v, line.number));
                }
                self.pos += 1;
            }
        }
    }

    /// The value of a mapping entry: a scalar, a flow sequence, a block scalar, or a nested block.
    fn value(&mut self, child: &str, value: &str, indent: usize, number: usize) {
        if value.is_empty() {
            if let Some(next) = self.next_content() {
                if next.indent > indent {
                    self.block(child);
                } else if next.indent == indent && is_dash(&next.text) {
                    self.sequence(child, indent);
                }
            }
            return;
        }
        if value.starts_with('|') || value.starts_with('>') {
            let folded = value.starts_with('>');
            let mut parts: Vec<String> = Vec::new();
            let mut body_indent: Option<usize> = None;
            while self.pos < self.lines.len() {
                let line = &self.lines[self.pos];
                if line.indent == usize::MAX {
                    parts.push(String::new());
                    self.pos += 1;
                    continue;
                }
                if line.indent <= indent {
                    break;
                }
                let bi = *body_indent.get_or_insert(line.indent);
                parts.push(line.raw.get(bi.min(line.raw.len())..).unwrap_or("").to_string());
                self.pos += 1;
            }
            while parts.last().is_some_and(String::is_empty) {
                parts.pop();
            }
            let joined = if folded { parts.join(" ") } else { parts.join("\n") };
            self.out.push((child.to_string(), joined, number));
            return;
        }
        if let Some(inner) = value.strip_prefix('[').and_then(|v| v.strip_suffix(']')) {
            for (i, item) in inner.split(',').enumerate() {
                if let Some(v) = scalar(item) {
                    self.out.push((format!("{child}[{i}]"), v, number));
                }
            }
            return;
        }
        if let Some(v) = scalar(value) {
            self.out.push((child.to_string(), v, number));
        }
    }
}

// ---------------------------------------------------------------------------------------------------------------
// Configuration metadata

/// A type name with simple names: `java.util.List<java.lang.String>` → `List<String>`, `a.b.C$D` → `C$D`.
pub fn simple_type(ty: &str) -> String {
    let mut out = String::new();
    let mut word = String::new();
    for c in ty.chars() {
        if c.is_alphanumeric() || c == '_' || c == '$' {
            word.push(c);
        } else if c == '.' {
            if word.chars().next().is_some_and(|f| f.is_ascii_lowercase()) {
                word.clear();
            } else {
                word.push('.');
            }
        } else {
            out.push_str(&word);
            word.clear();
            out.push(c);
        }
    }
    out.push_str(&word);
    out.replace(", ", ",").replace(',', ", ")
}

fn shape_of_type(ty: &str) -> Shape {
    let base = ty.split('<').next().unwrap_or(ty);
    if ty.ends_with("[]") {
        return Shape::List;
    }
    match base {
        "java.util.Map" | "java.util.Properties" | "Map" | "Properties" => Shape::Map,
        "java.util.List" | "java.util.Set" | "java.util.Collection" | "List" | "Set" | "Collection" | "Iterable" | "java.lang.Iterable" => Shape::List,
        _ => Shape::Exact,
    }
}

/// The element type of a list (`List<String>` → `String`, `String[]` → `String`) or the value type of a map.
fn element_type(ty: &str) -> Option<String> {
    if let Some(inner) = ty.strip_suffix("[]") {
        return Some(inner.to_string());
    }
    let inner = ty.find('<').map(|i| &ty[i + 1..ty.len() - 1])?;
    let mut depth = 0;
    let mut last = 0;
    for (i, c) in inner.char_indices() {
        match c {
            '<' => depth += 1,
            '>' => depth -= 1,
            ',' if depth == 0 => last = i + 1,
            _ => {}
        }
    }
    Some(inner[last..].trim().to_string())
}

/// Every key the class path's configuration metadata declares, canonical, with Boot's `ignored` properties as
/// maps of keys that are known not to bind.
pub fn metadata(cp: &ClassPath) -> Result<BTreeMap<String, Declared>, Error> {
    let mut out: BTreeMap<String, Declared> = BTreeMap::new();
    for name in METADATA {
        for (entry, bytes) in cp.resources(name)? {
            let json: serde_json::Value = match serde_json::from_slice(&bytes) {
                Ok(v) => v,
                Err(e) => return Err(Error::new(format!("{entry}!{name}: {e}"))),
            };
            for p in json.get("properties").and_then(|p| p.as_array()).into_iter().flatten() {
                let Some(key) = p.get("name").and_then(|n| n.as_str()) else { continue };
                let ty = p.get("type").and_then(|t| t.as_str()).map(str::to_string);
                let deprecation = p.get("deprecation").map(|d| Deprecation {
                    level: d.get("level").and_then(|l| l.as_str()).unwrap_or("warning").to_string(),
                    replacement: d.get("replacement").and_then(|r| r.as_str()).map(str::to_string),
                    since: d.get("since").and_then(|r| r.as_str()).map(str::to_string),
                    reason: d.get("reason").and_then(|r| r.as_str()).map(str::to_string),
                });
                let deprecation = deprecation.or_else(|| p.get("deprecated").and_then(|d| d.as_bool()).filter(|d| *d).map(|_| Deprecation { level: "warning".into(), ..Default::default() }));
                let declared = Declared { shape: ty.as_deref().map(shape_of_type).unwrap_or(Shape::Exact), ty, source: p.get("sourceType").and_then(|s| s.as_str()).map(str::to_string), deprecation };
                let key = canonical(key);
                match out.get(&key) {
                    // The first declaration wins, unless it said less.
                    Some(existing) if existing.ty.is_some() || declared.ty.is_none() => {}
                    _ => {
                        out.insert(key, declared);
                    }
                }
            }
            for p in json.get("ignored").and_then(|i| i.get("properties")).and_then(|p| p.as_array()).into_iter().flatten() {
                if let Some(key) = p.get("name").and_then(|n| n.as_str()) {
                    out.entry(canonical(key)).or_insert(Declared { shape: Shape::Map, ..Default::default() });
                }
            }
        }
    }
    Ok(out)
}

// ---------------------------------------------------------------------------------------------------------------
// What the classes read

/// `${key}` and `${key:default}` in a string, outermost first; a default that is itself a placeholder yields its
/// key too, with no default.
pub fn placeholders(s: &str) -> Vec<(String, Option<String>)> {
    let mut out = Vec::new();
    let bytes = s.as_bytes();
    let mut i = 0;
    while i + 1 < bytes.len() {
        if bytes[i] == b'$' && bytes[i + 1] == b'{' {
            let mut depth = 0;
            let mut j = i + 1;
            let mut end = None;
            while j < bytes.len() {
                match bytes[j] {
                    b'{' => depth += 1,
                    b'}' => {
                        depth -= 1;
                        if depth == 0 {
                            end = Some(j);
                            break;
                        }
                    }
                    _ => {}
                }
                j += 1;
            }
            let Some(end) = end else { break };
            let inner = &s[i + 2..end];
            let mut depth = 0;
            let mut split = None;
            for (k, c) in inner.char_indices() {
                match c {
                    '{' => depth += 1,
                    '}' => depth -= 1,
                    ':' if depth == 0 => {
                        split = Some(k);
                        break;
                    }
                    _ => {}
                }
            }
            let (key, default) = match split {
                Some(k) => (&inner[..k], Some(inner[k + 1..].to_string())),
                None => (inner, None),
            };
            out.push((key.trim().to_string(), default.clone()));
            if let Some(d) = &default {
                out.extend(placeholders(d).into_iter().map(|(k, _)| (k, None)));
            }
            i = end + 1;
        } else {
            i += 1;
        }
    }
    out
}

fn element_strings(value: &ElementValue, out: &mut Vec<String>) {
    match value {
        ElementValue::String(s) => out.push(s.clone()),
        ElementValue::Array(items) => items.iter().for_each(|v| element_strings(v, out)),
        ElementValue::Annotation(a) => a.elements.iter().for_each(|(_, v)| element_strings(v, out)),
        _ => {}
    }
}

/// The class a field's type names, from its descriptor.
fn field_class(field: &Field) -> Option<String> {
    field.descriptor.strip_prefix('L').and_then(|d| d.strip_suffix(';')).map(str::to_string)
}

fn simple_class(internal: &str) -> String {
    internal.rsplit('/').next().unwrap_or(internal).to_string()
}

fn method_label(class: &ClassFile, method: &crate::classfile::Method) -> String {
    let params = MethodDescriptor::parse(&method.descriptor).map(|d| d.params.iter().map(Type::simple_name).collect::<Vec<_>>().join(", ")).unwrap_or_default();
    format!("{}.{}({params})", simple_class(&class.name), method.name)
}

struct Scan<'a> {
    cp: &'a ClassPath,
    local: Option<&'a BTreeSet<String>>,
    out: Vec<Binding>,
}

impl Scan<'_> {
    fn is_local(&self, name: &str) -> bool {
        self.local.is_none_or(|l| l.contains(name)) && self.cp.is_application(name)
    }

    /// The placeholders in an annotation's strings. `@Scheduled`'s strings are durations (or a cron expression);
    /// `@Value`'s bind to the annotated member's type; anything else reads a string.
    fn annotation(&mut self, a: &Annotation, class: &ClassFile, site: &str, ty: Option<(String, Option<String>)>, line: Option<u16>) {
        let name = a.simple_name();
        for (element, value) in &a.elements {
            let mut strings = Vec::new();
            element_strings(value, &mut strings);
            let ty = match name.as_str() {
                "Scheduled" if element == "cron" => Some(("cron expression".to_string(), None)),
                "Scheduled" => Some(("Duration".to_string(), None)),
                "Value" => ty.clone(),
                _ => None,
            };
            for s in strings {
                for (key, default) in placeholders(&s) {
                    self.out.push(Binding { key, shape: Shape::Exact, ty: ty.as_ref().map(|t| t.0.clone()), ty_class: ty.as_ref().and_then(|t| t.1.clone()), default, site: format!("@{name} {site}"), class: class.name.clone(), line });
                }
            }
        }
        if name == "ConditionalOnProperty" || name == "ConditionalOnBooleanProperty" {
            let prefix = a.strings("prefix").into_iter().next().unwrap_or_default();
            let mut names = a.strings("name");
            names.extend(a.strings("value"));
            for n in names {
                let key = if prefix.is_empty() { n } else { format!("{}.{n}", prefix.trim_end_matches('.')) };
                let ty = if name == "ConditionalOnBooleanProperty" { "boolean" } else { "String" };
                let having = a.strings("havingValue").into_iter().next();
                let site = match having {
                    Some(h) => format!("@{name}(havingValue = {h:?}) {site}"),
                    None => format!("@{name} {site}"),
                };
                self.out.push(Binding { key, shape: Shape::Exact, ty: Some(ty.to_string()), ty_class: None, default: None, site, class: class.name.clone(), line });
            }
        }
    }

    /// The keys a `@ConfigurationProperties` type binds under its prefix, one per field, following nested local
    /// types; a list field binds `key[]`, a map field `key.*`.
    fn properties(&mut self, class: &ClassFile, prefix: &str, site_prefix: &str, visited: &mut Vec<String>) {
        if visited.contains(&class.name) || visited.len() > 6 {
            return;
        }
        visited.push(class.name.clone());
        for field in &class.fields {
            if field.is_static() || field.access & flags::SYNTHETIC != 0 {
                continue;
            }
            let ty = wire::field_type_name(class, field);
            let key = if prefix.is_empty() { canonical(&field.name) } else { format!("{prefix}.{}", canonical(&field.name)) };
            let site = format!("{site_prefix} {}.{}", simple_class(&class.name), field.name);
            let line = None;
            match field_class(field) {
                Some(c) if self.is_local(&c) => {
                    if let Ok(Some(nested)) = self.cp.application(&c) {
                        if !nested.is_enum() && nested.access & flags::INTERFACE == 0 {
                            self.properties(&nested, &key, site_prefix, visited);
                            continue;
                        }
                    }
                    self.out.push(Binding { key, shape: Shape::Exact, ty: Some(ty), ty_class: Some(c), default: None, site, class: class.name.clone(), line });
                }
                Some(c) => {
                    let shape = shape_of_type(&c.replace('/', "."));
                    self.out.push(Binding { key, shape, ty: Some(ty), ty_class: Some(c), default: None, site, class: class.name.clone(), line });
                }
                None => {
                    let shape = if field.descriptor.starts_with('[') { Shape::List } else { Shape::Exact };
                    self.out.push(Binding { key, shape, ty: Some(ty), ty_class: None, default: None, site, class: class.name.clone(), line });
                }
            }
        }
        visited.pop();
    }

    fn class(&mut self, class: &ClassFile) -> Result<(), Error> {
        let name = &class.name;
        let class_site = format!("on {}", simple_class(name));
        let annotations = class.annotations().map_err(|e| Error::new(format!("{name}: {e}")))?;
        for a in &annotations {
            self.annotation(a, class, &class_site, None, None);
            if a.simple_name() == "ConfigurationProperties" {
                let prefix = canonical(&a.strings("prefix").into_iter().chain(a.strings("value")).next().unwrap_or_default());
                let site_prefix = if prefix.is_empty() { "@ConfigurationProperties".to_string() } else { format!("@ConfigurationProperties({prefix:?})") };
                self.properties(class, &prefix, &site_prefix, &mut Vec::new());
            }
        }
        for field in &class.fields {
            if field.access & flags::SYNTHETIC != 0 {
                continue;
            }
            let ty = Some((wire::field_type_name(class, field), field_class(field)));
            for a in field.annotations(&class.pool).map_err(|e| Error::new(format!("{name}: {e}")))? {
                self.annotation(&a, class, &format!("on {}.{}", simple_class(name), field.name), ty.clone(), None);
            }
        }
        for method in &class.methods {
            if method.is_synthetic() || method.is_bridge() {
                continue;
            }
            let label = if method.is_constructor() { format!("{}(...)", simple_class(name)) } else { method_label(class, method) };
            let site = format!("in {label}");
            let line = method.first_line();
            let annotations = method.annotations(&class.pool).map_err(|e| Error::new(format!("{name}: {e}")))?;
            for a in &annotations {
                self.annotation(a, class, &site, None, line);
                if a.simple_name() == "ConfigurationProperties" {
                    let prefix = canonical(&a.strings("prefix").into_iter().chain(a.strings("value")).next().unwrap_or_default());
                    let returned = MethodDescriptor::parse(&method.descriptor).ok().and_then(|d| match d.ret {
                        Type::Object(c) => Some(c),
                        _ => None,
                    });
                    if let Some(c) = returned.filter(|c| self.is_local(c)) {
                        if let Ok(Some(bound)) = self.cp.application(&c) {
                            let site_prefix = format!("@ConfigurationProperties({prefix:?}) {site}:");
                            self.properties(&bound, &prefix, &site_prefix, &mut Vec::new());
                        }
                    }
                }
            }
            let Ok(d) = MethodDescriptor::parse(&method.descriptor) else { continue };
            let parameters = method.parameter_annotations(&class.pool).map_err(|e| Error::new(format!("{name}: {e}")))?;
            let names = method.parameter_names(&class.pool);
            for (i, list) in parameters.iter().enumerate() {
                let Some(t) = d.params.get(i) else { continue };
                let ty_class = match t {
                    Type::Object(c) => Some(c.clone()),
                    _ => None,
                };
                let pname = names.get(i).cloned().unwrap_or_else(|| format!("arg{i}"));
                for a in list {
                    self.annotation(a, class, &format!("in {label}, {pname}"), Some((t.simple_name(), ty_class.clone())), line);
                }
            }
            self.lookups(class, method);
        }
        Ok(())
    }

    /// `environment.getProperty("key")`, `getRequiredProperty`, `containsProperty`, with the key a constant.
    fn lookups(&mut self, class: &ClassFile, method: &crate::classfile::Method) {
        let Some(code) = &method.code else { return };
        let Ok(insns) = code.instructions() else { return };
        let targets = crate::boundaries::jump_targets(&insns, method);
        for (i, (pc, insn)) in insns.iter().enumerate() {
            let index = match insn {
                Insn::InvokeVirtual(i) | Insn::InvokeInterface(i) => *i,
                _ => continue,
            };
            let Ok(member) = class.pool.member(index) else { continue };
            if !member.owner.starts_with("org/springframework/core/env/") || !matches!(member.name.as_str(), "getProperty" | "getRequiredProperty" | "containsProperty") {
                continue;
            }
            let Ok(d) = MethodDescriptor::parse(&member.descriptor) else { continue };
            let n = d.params.len();
            let constant = |k: usize| -> Option<String> {
                let at = crate::boundaries::pushing(class, &insns, &targets, i, n - 1 - k)?;
                match insns[at].1 {
                    Insn::Ldc(c) => match class.pool.get(c).ok()? {
                        Constant::String { string_index } => class.pool.utf8(*string_index).ok().map(str::to_string),
                        Constant::Class { name_index } => class.pool.utf8(*name_index).ok().map(|s| format!("class {s}")),
                        _ => None,
                    },
                    _ => None,
                }
            };
            let Some(key) = constant(0) else { continue };
            if key.starts_with("class ") || key.contains("${") {
                continue;
            }
            let mut ty = Some("String".to_string());
            let mut ty_class = None;
            let mut default = None;
            if let Some(Type::Object(c)) = d.params.get(1) {
                if c == "java/lang/Class" {
                    if let Some(cls) = constant(1).and_then(|c| c.strip_prefix("class ").map(str::to_string)) {
                        ty = Some(simple_class(&cls).replace('$', "."));
                        ty_class = Some(cls);
                    } else {
                        ty = None;
                    }
                } else if c == "java/lang/String" {
                    default = constant(1);
                }
            }
            if n == 3 {
                default = constant(2);
            }
            let site = format!("Environment.{} in {}", member.name, method_label(class, method));
            self.out.push(Binding { key, shape: Shape::Exact, ty, ty_class, default, site, class: class.name.clone(), line: code.line_at(*pc).or(method.first_line()) });
        }
    }
}

/// Every key the local classes read, in class order.
pub fn bindings(cp: &ClassPath, local: Option<&BTreeSet<String>>) -> Result<Vec<Binding>, Error> {
    let mut scan = Scan { cp, local, out: Vec::new() };
    for (name, class) in cp.application_classes()? {
        if local.is_some_and(|l| !l.contains(&name)) || class.access & flags::ANNOTATION != 0 {
            continue;
        }
        scan.class(&class)?;
    }
    Ok(scan.out)
}

// ---------------------------------------------------------------------------------------------------------------
// Value checks

fn is_integer(v: &str) -> bool {
    let v = v.strip_prefix(['+', '-']).unwrap_or(v);
    !v.is_empty() && v.chars().all(|c| c.is_ascii_digit())
}

fn ends_with_unit(v: &str, units: &[&str]) -> bool {
    let lower = v.to_ascii_lowercase();
    let lower = lower.strip_prefix(['+', '-']).unwrap_or(&lower);
    if is_integer(lower) {
        return true;
    }
    units.iter().any(|u| lower.strip_suffix(u).is_some_and(|n| is_integer(n)))
}

/// Why `value` is not a `ty`, if it is not; `None` when it is, or when the type is not one the check knows.
fn mismatch(cp: &ClassPath, value: &str, ty: &str, ty_class: Option<&str>) -> Option<String> {
    if value.contains("${") || value.contains("#{") {
        return None;
    }
    let simple = simple_type(ty);
    let ok = match simple.as_str() {
        "int" | "Integer" | "long" | "Long" | "short" | "Short" | "byte" | "Byte" | "BigInteger" => is_integer(value),
        "float" | "double" | "Float" | "Double" | "BigDecimal" => value.parse::<f64>().is_ok(),
        "boolean" | "Boolean" => matches!(value.to_ascii_lowercase().as_str(), "true" | "false" | "on" | "off" | "yes" | "no" | "1" | "0"),
        "Duration" => value.to_ascii_uppercase().starts_with('P') || value.to_ascii_uppercase().starts_with("-P") || ends_with_unit(value, &["ns", "us", "ms", "s", "m", "h", "d"]),
        "DataSize" => ends_with_unit(value, &["b", "kb", "mb", "gb", "tb"]),
        "Period" => value.to_ascii_uppercase().starts_with('P') || ends_with_unit(value, &["y", "m", "w", "d"]),
        _ => {
            let class = ty_class.map(str::to_string).or_else(|| if ty.contains('.') && !ty.contains('<') { Some(ty.replace('.', "/")) } else { None });
            let class = class.and_then(|c| cp.load(&c).ok().flatten().map(|l| l.class)).filter(|c| c.is_enum())?;
            let constants: Vec<String> = class.fields.iter().filter(|f| f.is_static() && f.descriptor == format!("L{};", class.name)).map(|f| f.name.clone()).collect();
            let wanted = canonical(value).replace('-', "");
            if constants.iter().any(|c| canonical(c).replace('-', "") == wanted) {
                return None;
            }
            return Some(format!("{value:?} is not a {}: one of {}", simple_class(&class.name).replace('$', "."), constants.join(", ")));
        }
    };
    (!ok).then(|| format!("{value:?} is not a {simple}"))
}

fn distance(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    let mut previous: Vec<usize> = (0..=b.len()).collect();
    for i in 1..=a.len() {
        let mut current = vec![i; b.len() + 1];
        for j in 1..=b.len() {
            let cost = usize::from(a[i - 1] != b[j - 1]);
            current[j] = (previous[j] + 1).min(current[j - 1] + 1).min(previous[j - 1] + cost);
        }
        previous = current;
    }
    previous[b.len()]
}

// ---------------------------------------------------------------------------------------------------------------
// The block

/// One key of the configuration block as it is assembled.
#[derive(Default)]
struct Key {
    /// The line's key: canonical, with `[]` for a list binding and `.*` for a map.
    display: String,
    ty: Option<String>,
    ty_class: Option<String>,
    default: Option<String>,
    /// `(profile, value)` from the files, default profile first.
    values: Vec<(Option<String>, String)>,
    details: Vec<String>,
    problems: Vec<String>,
    source: Option<(PathBuf, usize)>,
    class: Option<String>,
    line: Option<u16>,
}

fn quote(value: &str) -> String {
    if value.is_empty() || value.chars().any(|c| c.is_whitespace() || c == '"' || c.is_control()) {
        format!("{value:?}")
    } else {
        value.to_string()
    }
}

/// The configuration block of a module: `None` when it has neither application files nor keys read by its
/// classes. The header names the files; each member is one key.
pub fn analyse(cp: &ClassPath, local: Option<&BTreeSet<String>>, resources: &[PathBuf]) -> Result<Option<(String, Bean)>, Error> {
    let (files, settings) = read_files(resources)?;
    let bindings = bindings(cp, local)?;
    if files.is_empty() && bindings.is_empty() {
        return Ok(None);
    }
    let declared = metadata(cp)?;
    let local_class = |c: &str| local.is_none_or(|l| l.contains(c)) && cp.is_application(c);

    let mut keys: BTreeMap<String, Key> = BTreeMap::new();
    // The keys the code reads: exact ones as lines, lists and maps as patterns and lines.
    let mut patterns: Vec<(String, Shape, Option<String>, String)> = Vec::new();
    for b in &bindings {
        let key = canonical(&b.key);
        let id = match b.shape {
            Shape::Exact => key.clone(),
            Shape::List => format!("{key}[]"),
            Shape::Map => format!("{key}.*"),
        };
        if b.shape != Shape::Exact {
            patterns.push((key.clone(), b.shape, b.ty.as_deref().and_then(element_type), b.site.clone()));
        }
        let entry = keys.entry(id.clone()).or_default();
        entry.display = id;
        if entry.ty.is_none() {
            entry.ty = b.ty.clone();
            entry.ty_class = b.ty_class.clone();
        }
        if entry.default.is_none() {
            entry.default = b.default.clone();
        }
        if let (Some(d), Some(t)) = (&b.default, &b.ty) {
            if let Some(why) = mismatch(cp, d, t, b.ty_class.as_deref()) {
                let problem = format!("! the default {why}");
                if !entry.problems.contains(&problem) {
                    entry.problems.push(problem);
                }
            }
        }
        let detail = match &b.default {
            Some(d) if b.shape == Shape::Exact => format!("{}, default {}", b.site, quote(d)),
            _ => b.site.clone(),
        };
        if !entry.details.contains(&detail) {
            entry.details.push(detail);
        }
        if entry.class.is_none() {
            entry.class = Some(b.class.clone());
            entry.line = b.line;
        }
    }
    for (key, d) in &declared {
        if d.shape != Shape::Exact {
            patterns.push((key.clone(), d.shape, d.ty.as_deref().and_then(element_type), String::new()));
        }
    }
    // Longest pattern first, so that `a.b.*` wins over `a.*`.
    patterns.sort_by(|x, y| y.0.len().cmp(&x.0.len()));

    let known: Vec<String> = keys.keys().filter(|k| !k.ends_with("[]") && !k.ends_with(".*")).cloned().chain(declared.iter().filter(|(_, d)| d.deprecation.is_none()).map(|(k, _)| k.clone())).collect();

    for s in &settings {
        let value_problem = |ty: Option<&str>, ty_class: Option<&str>| -> Option<String> {
            let why = mismatch(cp, &s.value, ty?, ty_class)?;
            Some(match &s.profile {
                Some(p) => format!("! {p}: {why}"),
                None => format!("! {why}"),
            })
        };
        let mut found: Option<&mut Key> = None;
        let mut problems: Vec<String> = Vec::new();
        let mut details: Vec<String> = Vec::new();
        let mut ty: Option<String> = None;
        let mut ty_class: Option<String> = None;
        if keys.contains_key(&s.key) {
            found = keys.get_mut(&s.key);
        }
        if found.is_none() {
            if let Some(d) = declared.get(&s.key) {
                ty = d.ty.clone();
                if let Some(dep) = &d.deprecation {
                    let mut text = String::from("! deprecated");
                    if let Some(since) = &dep.since {
                        text.push_str(&format!(" since {since}"));
                    }
                    if dep.level == "error" {
                        text.push_str(", no longer bound");
                    }
                    if let Some(r) = &dep.replacement {
                        text.push_str(&format!(": use {r}"));
                    } else if let Some(r) = &dep.reason {
                        text.push_str(&format!(": {r}"));
                    }
                    problems.push(text);
                }
                if let Some(src) = &d.source {
                    if !local_class(&src.replace('.', "/")) {
                        details.push(format!("declared by {}", simple_type(src)));
                    }
                }
            } else if let Some((base, shape, element, site)) = patterns.iter().find(|(base, shape, _, _)| match shape {
                Shape::List => without_index(&s.key) == Some(base.as_str()) || s.key == *base,
                Shape::Map => s.key.starts_with(&format!("{base}.")) || s.key.starts_with(&format!("{base}[")) || s.key == *base,
                Shape::Exact => false,
            }) {
                ty = element.clone();
                if s.key == *base {
                    // A list given as one comma-separated scalar, or a map set to one value.
                    ty = match shape {
                        Shape::List => element.as_ref().map(|e| format!("List<{e}>")),
                        _ => None,
                    };
                }
                if !site.is_empty() {
                    details.push(format!("under {} ({site})", if *shape == Shape::List { format!("{base}[]") } else { format!("{base}.*") }));
                } else if let Some(src) = declared.get(base).and_then(|d| d.source.as_ref()) {
                    details.push(format!("under {}, declared by {}", if *shape == Shape::List { format!("{base}[]") } else { format!("{base}.*") }, simple_type(src)));
                }
            } else {
                let mut text = String::from("! nothing binds it: no class on the class path reads it and no configuration metadata declares it");
                let nearest = known.iter().filter(|k| parent(k) == parent(&s.key) || parent(k).is_none()).map(|k| (distance(k, &s.key), k)).filter(|(d, _)| *d <= 2).min();
                if let Some((_, k)) = nearest {
                    text.push_str(&format!("; nearest known key: {k}"));
                }
                problems.push(text);
            }
            let entry = keys.entry(s.key.clone()).or_default();
            entry.display = s.key.clone();
            if entry.ty.is_none() {
                entry.ty = ty;
                entry.ty_class = ty_class.take();
            }
            for d in details {
                if !entry.details.contains(&d) {
                    entry.details.push(d);
                }
            }
            for p in problems {
                if !entry.problems.contains(&p) {
                    entry.problems.push(p);
                }
            }
            found = Some(entry);
        }
        let entry = found.expect("found or created");
        if let Some(p) = value_problem(entry.ty.as_deref(), entry.ty_class.as_deref()) {
            if !entry.problems.contains(&p) {
                entry.problems.push(p);
            }
        }
        entry.values.push((s.profile.clone(), s.value.clone()));
        if entry.source.is_none() && s.profile.is_none() {
            entry.source = Some((s.file.clone(), s.line));
        }
    }

    let members = keys
        .into_iter()
        .map(|(_, k)| {
            let mut line = k.display.clone();
            if let Some(t) = &k.ty {
                line.push_str(&format!(": {}", simple_type(t)));
            }
            let mut parts: Vec<String> = Vec::new();
            for (profile, value) in &k.values {
                match profile {
                    None => parts.push(format!("= {}", quote(value))),
                    Some(p) => parts.push(format!("{p}: {}", quote(value))),
                }
            }
            if k.values.is_empty() {
                if let Some(d) = &k.default {
                    parts.push(format!("default {}", quote(d)));
                }
            }
            if !parts.is_empty() {
                line.push(' ');
                line.push_str(&parts.join(", "));
            }
            let mut details = k.details;
            let problems = k.problems.len();
            details.extend(k.problems);
            Member { line, details, entry: false, advised: false, problems, source_line: k.source.as_ref().map(|(_, l)| (*l).min(u16::MAX as usize) as u16).or(k.line), source_file: k.source.map(|(f, _)| f), source_class: k.class }
        })
        .collect();
    let header = if files.is_empty() { "no application files".to_string() } else { files.join(", ") };
    Ok(Some((header, Bean { annotations: header, members })))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keys_are_relaxed_to_their_canonical_form() {
        assert_eq!(canonical("boxoffice.hold.maxSeats"), "boxoffice.hold.max-seats");
        assert_eq!(canonical("BOXOFFICE.HOLD.MAX_SEATS"), "boxoffice.hold.max-seats");
        assert_eq!(canonical("spring.kafka.producer.properties[enable.idempotence]"), "spring.kafka.producer.properties[enable.idempotence]");
        assert_eq!(canonical("servers[0].hostName"), "servers[0].host-name");
        assert_eq!(parent("a.b[0]"), Some("a.b"));
        assert_eq!(parent("a.b.c"), Some("a.b"));
    }

    #[test]
    fn yaml_documents_flatten_to_keys() {
        let text = "spring:\n  application:\n    name: ticketing # the name\n  kafka:\n    bootstrap-servers: localhost:9092\n    producer:\n      properties:\n        enable.idempotence: true\nlist:\n  - a\n  - \"b: c\"\nflow: [x, y]\nservers:\n- host: h1\n  port: 1\n- host: h2\nempty:\ntext: |\n  line one\n  line two\n---\nspring:\n  config:\n    activate:\n      on-profile: prod\nserver:\n  port: 80\n";
        let docs = yaml(text);
        assert_eq!(docs.len(), 2);
        let (profile, keys) = &docs[0];
        assert_eq!(profile.as_deref(), None);
        let get = |k: &str| keys.iter().find(|(key, _, _)| key == k).map(|(_, v, _)| v.clone());
        assert_eq!(get("spring.application.name").as_deref(), Some("ticketing"));
        assert_eq!(get("spring.kafka.bootstrap-servers").as_deref(), Some("localhost:9092"));
        assert_eq!(get("spring.kafka.producer.properties.enable.idempotence").as_deref(), Some("true"));
        assert_eq!(get("list[0]").as_deref(), Some("a"));
        assert_eq!(get("list[1]").as_deref(), Some("b: c"));
        assert_eq!(get("flow[1]").as_deref(), Some("y"));
        assert_eq!(get("servers[0].host").as_deref(), Some("h1"));
        assert_eq!(get("servers[0].port").as_deref(), Some("1"));
        assert_eq!(get("servers[1].host").as_deref(), Some("h2"));
        assert_eq!(get("empty"), None);
        assert_eq!(get("text").as_deref(), Some("line one\nline two"));
        assert_eq!(keys.iter().find(|(k, _, _)| k == "spring.application.name").map(|(_, _, l)| *l), Some(3));
        let (profile, keys) = &docs[1];
        assert_eq!(profile.as_deref(), Some("prod"));
        assert_eq!(keys.iter().find(|(k, _, _)| k == "server.port").map(|(_, v, _)| v.as_str()), Some("80"));
    }

    #[test]
    fn properties_files_flatten_too() {
        let docs = properties("# comment\nserver.port = 8080\nspring.application.name:app\nlong = a,\\\n  b\n#---\nspring.config.activate.on-profile=prod\nserver.port=80\n");
        assert_eq!(docs.len(), 2);
        assert_eq!(docs[0].1, vec![("server.port".to_string(), "8080".to_string(), 2), ("spring.application.name".to_string(), "app".to_string(), 3), ("long".to_string(), "a,b".to_string(), 4)]);
        assert_eq!(docs[1].0.as_deref(), Some("prod"));
    }

    #[test]
    fn placeholders_split_keys_and_defaults() {
        assert_eq!(placeholders("${a.b}"), vec![("a.b".to_string(), None)]);
        assert_eq!(placeholders("${a.b:8}"), vec![("a.b".to_string(), Some("8".to_string()))]);
        assert_eq!(placeholders("${a:${b:x}}"), vec![("a".to_string(), Some("${b:x}".to_string())), ("b".to_string(), None)]);
        assert_eq!(placeholders("x-${a}-${b}"), vec![("a".to_string(), None), ("b".to_string(), None)]);
        assert!(placeholders("#{systemProperties['x']}").is_empty());
    }

    #[test]
    fn values_are_checked_against_their_type() {
        let cp = ClassPath::new();
        assert_eq!(mismatch(&cp, "8", "int", None), None);
        assert_eq!(mismatch(&cp, "eight", "java.lang.Integer", None).as_deref(), Some("\"eight\" is not a Integer"));
        assert_eq!(mismatch(&cp, "2m", "java.time.Duration", None), None);
        assert_eq!(mismatch(&cp, "PT2M", "Duration", None), None);
        assert_eq!(mismatch(&cp, "2 minutes", "Duration", None).as_deref(), Some("\"2 minutes\" is not a Duration"));
        assert_eq!(mismatch(&cp, "10MB", "org.springframework.util.unit.DataSize", None), None);
        assert_eq!(mismatch(&cp, "on", "boolean", None), None);
        assert_eq!(mismatch(&cp, "${x}", "int", None), None);
        assert_eq!(mismatch(&cp, "anything", "java.lang.String", None), None);
        assert_eq!(simple_type("java.util.Map<java.lang.String,java.lang.String>"), "Map<String, String>");
        assert_eq!(simple_type("org.springframework.boot.kafka.autoconfigure.KafkaProperties$Producer"), "KafkaProperties$Producer");
        assert_eq!(element_type("java.util.Map<java.lang.String,java.util.List<java.lang.String>>").as_deref(), Some("java.util.List<java.lang.String>"));
        assert_eq!(distance("max-seat", "max-seats"), 1);
    }
}
