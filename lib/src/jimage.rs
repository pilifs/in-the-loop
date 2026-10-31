//! A reader for the JDK's `lib/modules` image (the `jimage` format), so that the JDK's own class files can be
//! consulted without starting a JVM: to resolve the hierarchy of JDK types, and to hand JBMC the real bytecode of
//! `java.lang.Math` instead of its models.
//!
//! The format (OpenJDK `imageFile.hpp`): a header, a redirect table and an offsets table of `table_length` entries
//! for perfect hashing, a location-attribute area, a string table, and the resources. Only the index (a few
//! megabytes) is read when the image is opened; each resource is read on demand. A resource may be stored
//! compressed; the `zip` compressor (zlib) is supported, the string-sharing one is not, and uncompressed images,
//! which `jlink` produces by default, need neither.

use std::cell::RefCell;
use std::collections::HashMap;
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};

use crate::Error;

const MAGIC: u32 = 0xCAFE_DADA;
const HEADER_SIZE: usize = 7 * 4;
const HASH_MULTIPLIER: i32 = 0x0100_0193;

#[derive(Debug, Clone, Copy, Default)]
struct Location {
    module: u32,
    parent: u32,
    base: u32,
    extension: u32,
    offset: u64,
    compressed: u64,
    uncompressed: u64,
}

/// An open JDK image.
pub struct JImage {
    file: RefCell<File>,
    /// The header and index: redirect table, offsets table, locations and strings.
    index: Vec<u8>,
    little_endian: bool,
    locations_start: usize,
    strings_start: usize,
    offsets_start: usize,
    /// Class name (`java/lang/Object`) to the index of its location in the offsets table.
    classes: HashMap<String, u32>,
}

impl JImage {
    /// Opens `<java_home>/lib/modules`.
    pub fn open(java_home: &Path) -> Result<JImage, Error> {
        let path = java_home.join("lib").join("modules");
        JImage::open_file(&path).map_err(|e| Error::new(format!("{}: {e}", path.display())))
    }

    /// Finds a JDK: `$JAVA_HOME`, or the home of the `java` on `$PATH`.
    pub fn find_java_home() -> Option<PathBuf> {
        if let Some(home) = std::env::var_os("JAVA_HOME") {
            let home = PathBuf::from(home);
            if home.join("lib").join("modules").exists() {
                return Some(home);
            }
        }
        let path = std::env::var_os("PATH")?;
        for dir in std::env::split_paths(&path) {
            let java = dir.join("java");
            if java.is_file() {
                let real = std::fs::canonicalize(&java).unwrap_or(java);
                if let Some(home) = real.parent().and_then(Path::parent) {
                    if home.join("lib").join("modules").exists() {
                        return Some(home.to_path_buf());
                    }
                }
            }
        }
        None
    }

    /// Opens the image of the JDK [`find_java_home`](Self::find_java_home) finds, if any.
    pub fn open_default() -> Option<JImage> {
        JImage::open(&JImage::find_java_home()?).ok()
    }

    fn open_file(path: &Path) -> Result<JImage, Error> {
        let mut file = File::open(path).map_err(|e| Error::new(format!("cannot open: {e}")))?;
        let mut header = [0u8; HEADER_SIZE];
        file.read_exact(&mut header).map_err(|_| Error::new("jimage: too short"))?;
        let raw_magic = u32::from_le_bytes([header[0], header[1], header[2], header[3]]);
        let little_endian = if raw_magic == MAGIC {
            true
        } else if raw_magic.swap_bytes() == MAGIC {
            false
        } else {
            return Err(Error::new("jimage: bad magic"));
        };
        let field = |at: usize| {
            let b = [header[at], header[at + 1], header[at + 2], header[at + 3]];
            if little_endian {
                u32::from_le_bytes(b)
            } else {
                u32::from_be_bytes(b)
            }
        };
        // Header: magic, version, flags, resource count, table length, locations size, strings size.
        let table_length = field(16) as usize;
        let locations_size = field(20) as usize;
        let strings_size = field(24) as usize;
        let offsets_start = HEADER_SIZE + table_length * 4;
        let locations_start = offsets_start + table_length * 4;
        let strings_start = locations_start + locations_size;
        let index_size = strings_start + strings_size;
        let mut index = vec![0u8; index_size];
        index[..HEADER_SIZE].copy_from_slice(&header);
        file.read_exact(&mut index[HEADER_SIZE..]).map_err(|_| Error::new("jimage: index larger than file"))?;
        let mut image = JImage { file: RefCell::new(file), index, little_endian, locations_start, strings_start, offsets_start, classes: HashMap::new() };
        let mut classes = HashMap::with_capacity(table_length);
        for i in 0..table_length {
            let location = image.location(i as u32)?;
            if image.string(location.extension)? != "class" {
                continue;
            }
            let parent = image.string(location.parent)?.into_owned();
            let base = image.string(location.base)?;
            let name = if parent.is_empty() { base.into_owned() } else { format!("{parent}/{base}") };
            classes.insert(name, i as u32);
        }
        image.classes = classes;
        Ok(image)
    }

    fn u32_at(&self, at: usize) -> Result<u32, Error> {
        let b = self.index.get(at..at + 4).ok_or_else(|| Error::new("jimage: truncated"))?;
        let bytes = [b[0], b[1], b[2], b[3]];
        Ok(if self.little_endian { u32::from_le_bytes(bytes) } else { u32::from_be_bytes(bytes) })
    }

    fn location(&self, index: u32) -> Result<Location, Error> {
        let offset = self.u32_at(self.offsets_start + index as usize * 4)? as usize;
        let mut pos = self.locations_start + offset;
        let mut loc = Location::default();
        loop {
            let byte = *self.index.get(pos).ok_or_else(|| Error::new("jimage: truncated location"))?;
            pos += 1;
            let kind = byte >> 3;
            if kind == 0 {
                break;
            }
            let length = (byte & 7) as usize + 1;
            let mut value: u64 = 0;
            for _ in 0..length {
                value = (value << 8) | u64::from(*self.index.get(pos).ok_or_else(|| Error::new("jimage: truncated location"))?);
                pos += 1;
            }
            match kind {
                1 => loc.module = value as u32,
                2 => loc.parent = value as u32,
                3 => loc.base = value as u32,
                4 => loc.extension = value as u32,
                5 => loc.offset = value,
                6 => loc.compressed = value,
                7 => loc.uncompressed = value,
                _ => return Err(Error::new(format!("jimage: unknown location attribute {kind}"))),
            }
        }
        Ok(loc)
    }

    /// A string of the table. They are modified UTF-8 (as in class files); the ones that matter here, module and
    /// class names, are ASCII, and anything else is decoded leniently.
    fn string(&self, offset: u32) -> Result<std::borrow::Cow<'_, str>, Error> {
        let start = self.strings_start + offset as usize;
        let rest = self.index.get(start..).ok_or_else(|| Error::new("jimage: bad string offset"))?;
        let end = rest.iter().position(|&b| b == 0).ok_or_else(|| Error::new("jimage: unterminated string"))?;
        Ok(match std::str::from_utf8(&rest[..end]) {
            Ok(s) => std::borrow::Cow::Borrowed(s),
            Err(_) => std::borrow::Cow::Owned(crate::classfile::decode_modified_utf8(&rest[..end])),
        })
    }

    /// The module a class lives in, such as `java.base`.
    pub fn module_of(&self, class_name: &str) -> Option<String> {
        let index = *self.classes.get(class_name)?;
        let location = self.location(index).ok()?;
        self.string(location.module).ok().map(|s| s.into_owned())
    }

    pub fn contains(&self, class_name: &str) -> bool {
        self.classes.contains_key(class_name)
    }

    /// Every class in the image, by internal name.
    pub fn class_names(&self) -> impl Iterator<Item = &str> {
        self.classes.keys().map(String::as_str)
    }

    fn read_resource(&self, offset: u64, length: usize) -> Result<Vec<u8>, Error> {
        let mut file = self.file.borrow_mut();
        file.seek(SeekFrom::Start(self.index.len() as u64 + offset)).map_err(|e| Error::new(format!("jimage: seek failed: {e}")))?;
        let mut bytes = vec![0u8; length];
        file.read_exact(&mut bytes).map_err(|_| Error::new("jimage: truncated resource"))?;
        Ok(bytes)
    }

    /// The bytes of a class file, by internal name (`java/lang/Math`).
    pub fn read_class(&self, class_name: &str) -> Result<Option<Vec<u8>>, Error> {
        let Some(&index) = self.classes.get(class_name) else {
            return Ok(None);
        };
        let location = self.location(index)?;
        if location.compressed == 0 {
            return Ok(Some(self.read_resource(location.offset, location.uncompressed as usize)?));
        }
        let mut bytes = self.read_resource(location.offset, location.compressed as usize)?;
        // Compression headers may be stacked; each is 29 bytes: magic, compressed size, uncompressed size,
        // decompressor name offset, decompressor config offset, is_terminal.
        loop {
            if bytes.len() < 29 || self.header_u32(&bytes, 0) != 0xCAFE_FAFA {
                return Ok(Some(bytes));
            }
            let compressed = self.header_u64(&bytes, 4) as usize;
            let decompressor = self.header_u32(&bytes, 20);
            let name = self.string(decompressor)?.into_owned();
            if name != "zip" {
                return Err(Error::new(format!("jimage: {class_name} is compressed with {name:?}, which is not supported")));
            }
            let payload = bytes.get(29..29 + compressed).ok_or_else(|| Error::new("jimage: truncated compressed resource"))?;
            let mut out = Vec::new();
            flate2::read::ZlibDecoder::new(payload).read_to_end(&mut out).map_err(|e| Error::new(format!("jimage: inflate failed: {e}")))?;
            bytes = out;
        }
    }

    fn header_u32(&self, bytes: &[u8], at: usize) -> u32 {
        let b = [bytes[at], bytes[at + 1], bytes[at + 2], bytes[at + 3]];
        if self.little_endian { u32::from_le_bytes(b) } else { u32::from_be_bytes(b) }
    }

    fn header_u64(&self, bytes: &[u8], at: usize) -> u64 {
        let mut b = [0u8; 8];
        b.copy_from_slice(&bytes[at..at + 8]);
        if self.little_endian { u64::from_le_bytes(b) } else { u64::from_be_bytes(b) }
    }

    /// The hash the image's perfect hash tables use, exposed for tests of the format.
    pub fn hash(name: &str, seed: i32) -> i32 {
        let mut hash = seed;
        for &byte in name.as_bytes() {
            hash = hash.wrapping_mul(HASH_MULTIPLIER) ^ i32::from(byte);
        }
        hash & 0x7FFF_FFFF
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_classes_from_the_local_jdk() {
        let Some(home) = JImage::find_java_home() else {
            eprintln!("no JDK found; skipping");
            return;
        };
        let image = JImage::open(&home).expect("the JDK image opens");
        assert_eq!(image.module_of("java/lang/Object").as_deref(), Some("java.base"));
        let bytes = image.read_class("java/lang/Math").unwrap().expect("java.lang.Math");
        let class = crate::classfile::ClassFile::parse(&bytes).unwrap();
        assert_eq!(class.name, "java/lang/Math");
        assert!(class.methods.iter().any(|m| m.name == "multiplyExact"));
        assert!(image.read_class("no/such/Class").unwrap().is_none());
        assert!(image.contains("java/util/List"));
    }
}
