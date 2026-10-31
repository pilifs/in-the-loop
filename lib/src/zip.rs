//! A minimal reader for zip archives (jars): the central directory, stored and deflated entries. It covers what a
//! jar built by any JVM tool contains; zip64 archives (over 4 GB or 65,535 entries) are rejected.

use std::collections::BTreeMap;
use std::io::Read;
use std::path::Path;

use crate::Error;

#[derive(Debug, Clone, Copy)]
struct Entry {
    method: u16,
    compressed_size: u32,
    uncompressed_size: u32,
    local_header_offset: u32,
}

/// A zip archive held in memory.
pub struct ZipArchive {
    data: Vec<u8>,
    entries: BTreeMap<String, Entry>,
}

const EOCD: u32 = 0x0605_4b50;
const CENTRAL: u32 = 0x0201_4b50;
const LOCAL: u32 = 0x0403_4b50;

fn u16_at(data: &[u8], at: usize) -> Result<u16, Error> {
    data.get(at..at + 2)
        .map(|b| u16::from_le_bytes([b[0], b[1]]))
        .ok_or_else(|| Error::new("zip: truncated archive"))
}

fn u32_at(data: &[u8], at: usize) -> Result<u32, Error> {
    data.get(at..at + 4)
        .map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
        .ok_or_else(|| Error::new("zip: truncated archive"))
}

impl ZipArchive {
    pub fn open(path: &Path) -> Result<ZipArchive, Error> {
        let data = std::fs::read(path).map_err(|e| Error::new(format!("cannot read {}: {e}", path.display())))?;
        ZipArchive::from_bytes(data).map_err(|e| Error::new(format!("{}: {e}", path.display())))
    }

    pub fn from_bytes(data: Vec<u8>) -> Result<ZipArchive, Error> {
        let len = data.len();
        if len < 22 {
            return Err(Error::new("zip: too short"));
        }
        let search_from = len.saturating_sub(22 + 65_535);
        let mut eocd = None;
        let mut at = len - 22;
        loop {
            if u32_at(&data, at)? == EOCD {
                eocd = Some(at);
                break;
            }
            if at == search_from {
                break;
            }
            at -= 1;
        }
        let eocd = eocd.ok_or_else(|| Error::new("zip: no end of central directory record"))?;
        let total = u16_at(&data, eocd + 10)?;
        let cd_size = u32_at(&data, eocd + 12)?;
        let cd_offset = u32_at(&data, eocd + 16)?;
        if total == 0xFFFF || cd_size == 0xFFFF_FFFF || cd_offset == 0xFFFF_FFFF {
            return Err(Error::new("zip: zip64 archives are not supported"));
        }
        let mut entries = BTreeMap::new();
        let mut pos = cd_offset as usize;
        for _ in 0..total {
            if u32_at(&data, pos)? != CENTRAL {
                return Err(Error::new("zip: bad central directory entry"));
            }
            let method = u16_at(&data, pos + 10)?;
            let compressed_size = u32_at(&data, pos + 20)?;
            let uncompressed_size = u32_at(&data, pos + 24)?;
            let name_len = u16_at(&data, pos + 28)? as usize;
            let extra_len = u16_at(&data, pos + 30)? as usize;
            let comment_len = u16_at(&data, pos + 32)? as usize;
            let local_header_offset = u32_at(&data, pos + 42)?;
            let name = data
                .get(pos + 46..pos + 46 + name_len)
                .ok_or_else(|| Error::new("zip: truncated entry name"))?;
            let name = String::from_utf8_lossy(name).into_owned();
            entries.insert(name, Entry { method, compressed_size, uncompressed_size, local_header_offset });
            pos += 46 + name_len + extra_len + comment_len;
        }
        Ok(ZipArchive { data, entries })
    }

    /// Entry names, sorted.
    pub fn names(&self) -> impl Iterator<Item = &str> {
        self.entries.keys().map(String::as_str)
    }

    pub fn contains(&self, name: &str) -> bool {
        self.entries.contains_key(name)
    }

    /// The uncompressed content of an entry, or `None` if there is no such entry.
    pub fn read(&self, name: &str) -> Result<Option<Vec<u8>>, Error> {
        let Some(entry) = self.entries.get(name) else {
            return Ok(None);
        };
        let at = entry.local_header_offset as usize;
        if u32_at(&self.data, at)? != LOCAL {
            return Err(Error::new(format!("zip: bad local header for {name}")));
        }
        let name_len = u16_at(&self.data, at + 26)? as usize;
        let extra_len = u16_at(&self.data, at + 28)? as usize;
        let start = at + 30 + name_len + extra_len;
        let end = start + entry.compressed_size as usize;
        let raw = self.data.get(start..end).ok_or_else(|| Error::new(format!("zip: truncated data for {name}")))?;
        match entry.method {
            0 => Ok(Some(raw.to_vec())),
            8 => {
                let mut out = Vec::with_capacity(entry.uncompressed_size as usize);
                flate2::read::DeflateDecoder::new(raw)
                    .read_to_end(&mut out)
                    .map_err(|e| Error::new(format!("zip: cannot inflate {name}: {e}")))?;
                Ok(Some(out))
            }
            other => Err(Error::new(format!("zip: unsupported compression method {other} for {name}"))),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    /// Builds a stored-entries zip by hand, to test the reader without a writer dependency.
    fn stored_zip(files: &[(&str, &[u8])]) -> Vec<u8> {
        let mut out = Vec::new();
        let mut central = Vec::new();
        for (name, content) in files {
            let offset = out.len() as u32;
            let crc = crc32(content);
            out.extend(LOCAL.to_le_bytes());
            out.extend([20, 0, 0, 0, 0, 0, 0, 0, 0, 0]); // version, flags, method 0, time, date
            out.extend(crc.to_le_bytes());
            out.extend((content.len() as u32).to_le_bytes());
            out.extend((content.len() as u32).to_le_bytes());
            out.extend((name.len() as u16).to_le_bytes());
            out.extend(0u16.to_le_bytes());
            out.extend(name.as_bytes());
            out.extend(*content);
            central.extend(CENTRAL.to_le_bytes());
            central.extend([20, 0, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
            central.extend(crc.to_le_bytes());
            central.extend((content.len() as u32).to_le_bytes());
            central.extend((content.len() as u32).to_le_bytes());
            central.extend((name.len() as u16).to_le_bytes());
            central.extend([0u8; 12]);
            central.extend(offset.to_le_bytes());
            central.extend(name.as_bytes());
        }
        let cd_offset = out.len() as u32;
        out.extend_from_slice(&central);
        out.extend(EOCD.to_le_bytes());
        out.extend([0, 0, 0, 0]);
        out.extend((files.len() as u16).to_le_bytes());
        out.extend((files.len() as u16).to_le_bytes());
        out.extend((central.len() as u32).to_le_bytes());
        out.extend(cd_offset.to_le_bytes());
        out.extend(0u16.to_le_bytes());
        out
    }

    fn crc32(data: &[u8]) -> u32 {
        let mut crc = 0xFFFF_FFFFu32;
        for &b in data {
            crc ^= u32::from(b);
            for _ in 0..8 {
                crc = if crc & 1 != 0 { (crc >> 1) ^ 0xEDB8_8320 } else { crc >> 1 };
            }
        }
        !crc
    }

    #[test]
    fn reads_stored_entries() {
        let zip = stored_zip(&[("a/B.class", b"hello"), ("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\n")]);
        let archive = ZipArchive::from_bytes(zip).unwrap();
        assert_eq!(archive.names().collect::<Vec<_>>(), vec!["META-INF/MANIFEST.MF", "a/B.class"]);
        assert_eq!(archive.read("a/B.class").unwrap().unwrap(), b"hello");
        assert!(archive.read("missing").unwrap().is_none());
    }

    #[test]
    fn reads_deflated_entries() {
        let mut encoder = flate2::write::DeflateEncoder::new(Vec::new(), flate2::Compression::default());
        encoder.write_all(b"deflated content, deflated content").unwrap();
        let compressed = encoder.finish().unwrap();
        let mut zip = stored_zip(&[("x", &compressed)]);
        // Patch the method fields (local header at 8, central entry at 10) to 8 = deflate.
        zip[8] = 8;
        let cd_offset = u32::from_le_bytes([zip[zip.len() - 6], zip[zip.len() - 5], zip[zip.len() - 4], zip[zip.len() - 3]]) as usize;
        zip[cd_offset + 10] = 8;
        let archive = ZipArchive::from_bytes(zip).unwrap();
        assert_eq!(archive.read("x").unwrap().unwrap(), b"deflated content, deflated content");
    }
}
