//! The built-in application loader, a fixed local classpath and the stock JAR handler.
//! Each enumeration has its own cursor. The pinned loader makes a new URL for every
//! hit. Connections and input streams are fresh, and the entry bytes are never exposed
//! as mutable backing storage. Only the supported public observations can reach them.
use super::*;
use crate::classfile::MemberRef;

const ENUM: &str = "java/lang/CompoundEnumeration";
const URL: &str = "java/net/URL";
const CONNECTION: &str = "sun/net/www/protocol/jar/JarURLConnection";
const STREAM: &str = "sun/net/www/protocol/jar/JarURLConnection$JarURLInputStream";
pub(super) const RESOURCE: &str = "<JDK.localJarResource>";
const POSITION: &str = "<JDK.resourcePosition>";
const CLOSED: &str = "<JDK.closed>";
const OPENED: &str = "<JDK.opened>";
const SOURCE_URL: &str = "<JDK.sourceURL>";
const URL_PATH: &str = "<JDK.jarURLPath>";
const READER: &str = "<JDK.privatePropertiesReader>";

impl Engine<'_> {
    pub(super) fn app_resources(&mut self, path: &mut Path, o: usize, m: &MemberRef, args: &[Val]) -> Option<Step> {
        if (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()) !=
            ("java/lang/ClassLoader", "getResources", "(Ljava/lang/String;)Ljava/util/Enumeration;")
            || self.gap_mode != GapMode::Strict || !self.contracts.is_empty() || self.previous.is_some()
            || path.literals.get(&Literal::Loader) != Some(&o) || !self.cp.jar_resource_image() { return None; }
        let [Val::R(Some(key))] = args else { return None };
        let name = String::from_utf16(&self.constant_units(path, *key)?).ok()?;
        let resources = self.cp.local_jar_resources(&name)?;
        if let Err(stop) = self.keeps(path, None, "consults the application class loader's resource cache") { return Some(Err(stop)); }
        let cursor = self.alloc(path, ENUM);
        let mut bindings = Vec::new();
        for (index, (provider, bytes)) in resources.into_iter().enumerate() {
            bindings.push(format!("{provider}:{}", crate::digest::sha256_hex(&bytes)));
            let data = self.alloc(path, "[B");
            path.objects[data].array = Some(Array { element: Type::Byte, length: self.b.constant(bytes.len() as i64, 32),
                cells: bytes.iter().map(|b| self.b.constant(i64::from(*b), 8)).collect(), refs: vec![] });
            if let Some(file) = self.cp.local_jar_url_path(provider, &name) {
                let text = self.string(path, &file.encode_utf16().collect::<Vec<_>>());
                path.objects[data].fields.insert(URL_PATH.into(), Val::R(Some(text)));
            }
            path.objects[cursor].fields.insert(format!("<url/{index}>"), Val::R(Some(data)));
        }
        path.objects[cursor].fields.insert(RESOURCE.into(), Val::I(self.b.constant(bindings.len() as i64, 32)));
        path.objects[cursor].fields.insert(POSITION.into(), Val::I(self.b.constant(0, 32)));
        self.assumed.insert(format!("the ordinary application loader reads fixed, valid local classpath entries with the stock JAR handler, no added or patched modules, boot append, instrumentation or security manager. The ordered {name} resources (classpath index and entry SHA-256) are [{}]", bindings.join(", ")));
        self.push(path, Val::R(Some(cursor)));
        self.advance(path);
        Some(Ok(None))
    }

    fn resource_object(&self, path: &mut Path, class: &str, bytes: Val) -> usize {
        let o = self.alloc(path, class);
        path.objects[o].fields.insert(RESOURCE.into(), bytes);
        path.objects[o].fields.insert(POSITION.into(), Val::I(self.b.constant(0, 32)));
        o
    }

    /// The pinned readLine refills only at the end of a window. In its ordinary loop,
    /// comment loop and CR lookahead, a positive refill preserves the next logical byte
    /// and EOF is tested at the same position. Only indices below its returned length
    /// are read. The size of a positive window (and the unspecified tail of an inflater
    /// buffer) is consequently invisible to this private consumer. Use one representative
    /// window. No other observer may use the physical stream position until the reader
    /// actually requests EOF, including when load exits early on a malformed escape.
    fn properties_refill(&mut self, path: &mut Path, stream: usize, buffer: usize, data: usize, pos: i64) -> Step {
        const PROPS: &str = "java/util/Properties";
        const LINE: &str = "java/util/Properties$LineReader";
        let [.., load, load0, line] = path.frames.as_slice() else { return unsupported("a bulk read outside the JDK properties reader"); };
        let Some(Some(Val::R(Some(reader)))) = line.locals.first() else { return unsupported("an unknown properties reader"); };
        let reader = *reader;
        if (line.class.name.as_str(), line.method.as_str(), line.code.descriptor.as_str()) != (LINE, "readLine", "()I")
            || (load0.class.name.as_str(), load0.method.as_str(), load0.code.descriptor.as_str()) != (PROPS, "load0", "(Ljava/util/Properties$LineReader;)V")
            || (load.class.name.as_str(), load.method.as_str(), load.code.descriptor.as_str()) != (PROPS, "load", "(Ljava/io/InputStream;)V")
            || !matches!(load.locals.first(), Some(Some(Val::R(Some(p)))) if path.objects[*p].class == PROPS)
            || path.objects[reader].class != LINE || !self.cp.properties_reader_image()
            || !matches!(path.objects[reader].fields.get("inStream"), Some(Val::R(Some(o))) if *o == stream)
            || !matches!(path.objects[reader].fields.get("inByteBuf"), Some(Val::R(Some(o))) if *o == buffer)
            || path.objects[stream].fields.get(READER).is_some_and(|r| !matches!(r, Val::R(Some(o)) if *o == reader)) {
            return unsupported("a bulk JAR read whose refill lengths are observable outside one private JDK properties reader");
        }
        let src = path.objects[data].as_array().ok_or_else(|| Stop::Unsupported("unknown resource bytes".into()))?;
        let dest = path.objects[buffer].as_array().ok_or_else(|| Stop::Unsupported("unknown properties buffer".into()))?;
        let cap = dest.cells.len();
        if dest.element != Type::Byte || cap != 8192 || self.b.constant_value(&dest.length) != Some(cap as i64) {
            return unsupported("a different JDK properties refill buffer");
        }
        let remaining = usize::try_from(pos).ok().and_then(|at| src.cells.get(at..))
            .ok_or_else(|| Stop::Unsupported("invalid JAR refill position".into()))?;
        self.keeps(path, Some(stream), "advances a properties input stream")?;
        let count = remaining.len().min(cap);
        let n = if count == 0 {
            path.objects[stream].fields.remove(READER);
            -1
        } else {
            self.keeps(path, Some(buffer), "refills the private properties buffer")?;
            let bytes = remaining[..count].to_vec();
            path.objects[buffer].array.as_mut().expect("checked buffer").cells[..count].clone_from_slice(&bytes);
            path.objects[stream].fields.insert(READER.into(), Val::R(Some(reader)));
            path.objects[stream].fields.insert(POSITION.into(), Val::I(self.b.constant(pos + count as i64, 32)));
            count as i64
        };
        self.push(path, Val::I(self.b.constant(n, 32)));
        self.advance(path);
        Ok(None)
    }

    pub(super) fn resource_call(&mut self, path: &mut Path, o: usize, m: &MemberRef, args: &[Val], special: bool) -> Step {
        let class = path.objects[o].class.clone();
        if special || !self.cp.is_subtype(&class, &m.owner) { return unsupported("incompatible call on a classpath resource"); }
        if self.there_before(path, o) { self.reads(path, || "reads a classpath resource object".into())?; }
        let fields = &path.objects[o].fields;
        let content = fields[RESOURCE].clone();
        let Val::I(position) = &fields[POSITION] else { return unsupported("an unknown resource cursor"); };
        let Some(pos) = self.b.constant_value(position) else { return unsupported("a symbolic resource cursor"); };
        if class == STREAM && m.name == "read" && m.descriptor == "([B)I" && !fields.contains_key(CLOSED) {
            if let ([Val::R(Some(buffer))], Val::R(Some(data))) = (args, &content) {
                return self.properties_refill(path, o, *buffer, *data, pos);
            }
        }
        if fields.contains_key(READER) {
            return unsupported("the JAR stream's physical cursor while a properties reader may hold unread bytes");
        }
        let result = match (class.as_str(), m.name.as_str(), m.descriptor.as_str(), args) {
            (_, "getClass", "()Ljava/lang/Class;", []) =>
                Some(Val::R(Some(self.literal(path, Literal::Class(class.clone()), "java/lang/Class")))),
            (ENUM, "hasMoreElements", "()Z", []) | (ENUM, "nextElement", "()Ljava/lang/Object;", []) => {
                let Val::I(count) = content else { return unsupported("unknown number of resource URLs"); };
                let Some(count) = self.b.constant_value(&count) else { return unsupported("a symbolic number of resource URLs"); };
                if m.name == "hasMoreElements" { Some(Val::I(self.b.constant(i64::from(pos < count), 32))) }
                else {
                    if pos >= count { return self.raise(path, "java/util/NoSuchElementException"); }
                    let Some(bytes) = fields.get(&format!("<url/{pos}>")).cloned() else { return unsupported("unbound resource URL"); };
                    self.keeps(path, Some(o), "advances a resource enumeration")?;
                    path.objects[o].fields.insert(POSITION.into(), Val::I(self.b.constant(pos + 1, 32)));
                    Some(Val::R(Some(self.resource_object(path, URL, bytes))))
                }
            }
            (URL, "getUserInfo", "()Ljava/lang/String;", []) => Some(Val::R(None)),
            (URL, "getPath" | "getFile", "()Ljava/lang/String;", []) => {
                let Val::R(Some(data)) = content else { return unsupported("unbound JAR resource"); };
                let Some(Val::R(Some(text))) = path.objects[data].fields.get(URL_PATH).cloned()
                    else { return unsupported("the canonical local JAR URL path needs an absolute unescaped classpath entry"); };
                let units = self.constant_units(path, text).ok_or_else(|| Stop::Unsupported("unbound JAR URL path".into()))?;
                let file = String::from_utf16(&units).map_err(|_| Stop::Unsupported("invalid JAR URL path".into()))?;
                self.assumed.insert(format!("the ordinary Unix application loader resolves this JAR entry at the same canonical URL path as the checker (UTF-8 SHA-256 {})", crate::digest::sha256_hex(file.as_bytes())));
                Some(Val::R(Some(text)))
            }
            (URL, "openConnection", "()Ljava/net/URLConnection;", []) => {
                self.keeps(path, None, "opens a local JAR resource connection")?;
                let con = self.resource_object(path, CONNECTION, content);
                path.objects[con].fields.insert(SOURCE_URL.into(), Val::R(Some(o)));
                Some(Val::R(Some(con)))
            }
            (CONNECTION, "getURL", "()Ljava/net/URL;", []) => Some(fields[SOURCE_URL].clone()),
            (URL, "openStream", "()Ljava/io/InputStream;", []) | (CONNECTION, "getInputStream", "()Ljava/io/InputStream;", []) => {
                if fields.contains_key(OPENED) { return unsupported("reopening a previously used JAR resource connection"); }
                self.keeps(path, None, "opens an input stream on a local JAR")?;
                if class == CONNECTION { path.objects[o].fields.insert(OPENED.into(), Val::I(self.b.constant(1, 32))); }
                Some(Val::R(Some(self.resource_object(path, STREAM, content))))
            }
            (STREAM, "close", "()V", []) => {
                if fields.contains_key(CLOSED) { return unsupported("closing a local JAR stream twice"); }
                self.keeps(path, None, "closes a local JAR input stream")?;
                path.objects[o].fields.insert(CLOSED.into(), Val::I(self.b.constant(1, 32)));
                None
            }
            (STREAM, "read", "()I", []) | (STREAM, "readAllBytes", "()[B", []) => {
                if fields.contains_key(CLOSED) { return unsupported("reading a closed local JAR stream"); }
                let Val::R(Some(data)) = content else { return unsupported("unbound JAR resource bytes"); };
                let cells = &path.objects[data].as_array().ok_or_else(|| Stop::Unsupported("unknown resource byte array".into()))?.cells;
                let Some(remaining) = usize::try_from(pos).ok().and_then(|n| cells.get(n..)) else { return unsupported("invalid resource cursor"); };
                let length = cells.len() as i64;
                self.keeps(path, Some(o), "reads a local JAR input stream")?;
                let (next, value) = if m.name == "read" {
                    match remaining.first() {
                        Some(byte) => (pos + 1, Val::I(self.b.zext(byte, 32))),
                        None => (pos, Val::I(self.b.constant(-1, 32))),
                    }
                } else {
                    let array = Array { element: Type::Byte, length: self.b.constant(remaining.len() as i64, 32), cells: remaining.to_vec(), refs: vec![] };
                    let copy = self.alloc(path, "[B");
                    path.objects[copy].array = Some(array);
                    (length, Val::R(Some(copy)))
                };
                path.objects[o].fields.insert(POSITION.into(), Val::I(self.b.constant(next, 32)));
                Some(value)
            }
            _ => return unsupported(format!("{}.{}{} on a classpath JAR resource at {}", class.replace('/', "."), m.name, m.descriptor,
                site(path.frames.last().expect("a frame")).display())),
        };
        if let Some(value) = result { self.push(path, value); }
        self.advance(path);
        Ok(None)
    }
}
