//! The class-file structures needed to bind instructions to their defining method.
//! The request assumes the JVM has verified types and instruction boundaries.
use super::{reject, unsupported, Result};

struct Reader<'a>(&'a [u8]);

impl<'a> Reader<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8]> {
        let (head, tail) = self
            .0
            .split_at_checked(n)
            .ok_or_else(|| reject("truncated class"))?;
        self.0 = tail;
        Ok(head)
    }
    fn u1(&mut self) -> Result<u8> {
        Ok(self.take(1)?[0])
    }
    fn u2(&mut self) -> Result<u16> {
        Ok(u16::from_be_bytes(self.take(2)?.try_into().unwrap()))
    }
    fn u4(&mut self) -> Result<usize> {
        Ok(u32::from_be_bytes(self.take(4)?.try_into().unwrap()) as usize)
    }
    fn attributes(&mut self) -> Result<Vec<(u16, &'a [u8])>> {
        (0..self.u2()?)
            .map(|_| {
                let key = self.u2()?;
                let n = self.u4()?;
                Ok((key, self.take(n)?))
            })
            .collect()
    }
    fn end(&self) -> Result<()> {
        if self.0.is_empty() {
            Ok(())
        } else {
            Err(reject("unconsumed class-file bytes"))
        }
    }
}

enum Cp<'a> {
    Other,
    Utf(&'a [u8]),
    Class(u16),
    NameType(u16, u16),
    Method(u16, u16),
}

pub struct Code<'a> {
    pub flags: u16,
    pub name: &'a str,
    pub desc: &'a str,
    pub bytes: &'a [u8],
    pub locals: u16,
    handlers: u16,
}

pub struct Class<'a> {
    cp: Vec<Cp<'a>>,
    pub owner: &'a str,
    pub parent: &'a str,
    methods: Vec<Code<'a>>,
}

impl<'a> Class<'a> {
    pub fn parse(bytes: &'a [u8]) -> Result<Self> {
        let mut r = Reader(bytes);
        if r.take(4)? != [0xca, 0xfe, 0xba, 0xbe] {
            return Err(reject("class magic"));
        }
        r.take(4)?;
        let count = r.u2()? as usize;
        let mut cp = vec![Cp::Other];
        while cp.len() < count {
            let entry = match r.u1()? {
                1 => {
                    let n = r.u2()? as usize;
                    Cp::Utf(r.take(n)?)
                }
                3 | 4 => {
                    r.take(4)?;
                    Cp::Other
                }
                5 | 6 => {
                    r.take(8)?;
                    cp.push(Cp::Other);
                    Cp::Other
                }
                7 => Cp::Class(r.u2()?),
                8 | 16 | 19 | 20 => {
                    r.take(2)?;
                    Cp::Other
                }
                9 | 11 | 17 | 18 => {
                    r.take(4)?;
                    Cp::Other
                }
                10 => Cp::Method(r.u2()?, r.u2()?),
                12 => Cp::NameType(r.u2()?, r.u2()?),
                15 => {
                    r.take(3)?;
                    Cp::Other
                }
                tag => return Err(unsupported(format!("constant pool tag {tag}"))),
            };
            cp.push(entry);
        }
        if cp.len() != count {
            return Err(reject("constant pool size"));
        }
        let flags = r.u2()?;
        if flags & 0x0200 != 0 {
            return Err(unsupported("interface declaration"));
        }
        let mut file = Class {
            cp,
            owner: "",
            parent: "",
            methods: vec![],
        };
        file.owner = file.class_name(r.u2()?)?;
        let parent = r.u2()?;
        if parent != 0 {
            file.parent = file.class_name(parent)?;
        }
        let interfaces = r.u2()? as usize;
        r.take(2 * interfaces)?;
        for _ in 0..r.u2()? {
            r.take(6)?;
            r.attributes()?;
        }
        for _ in 0..r.u2()? {
            let flags = r.u2()?;
            let name = file.utf(r.u2()?)?;
            let desc = file.utf(r.u2()?)?;
            for (key, data) in r.attributes()? {
                if file.utf(key)? != "Code" {
                    continue;
                }
                let mut body = Reader(data);
                body.u2()?;
                let locals = body.u2()?;
                let n = body.u4()?;
                let bytes = body.take(n)?;
                let handlers = body.u2()?;
                body.take(8 * usize::from(handlers))?;
                body.attributes()?;
                body.end()?;
                file.methods.push(Code {
                    flags,
                    name,
                    desc,
                    bytes,
                    locals,
                    handlers,
                });
            }
        }
        r.attributes()?;
        r.end()?;
        Ok(file)
    }
    fn utf(&self, i: u16) -> Result<&'a str> {
        match self.cp.get(i as usize) {
            Some(Cp::Utf(s)) => {
                std::str::from_utf8(s).map_err(|_| unsupported("non-UTF8 member identifier"))
            }
            _ => Err(reject("invalid constant-pool UTF8 index")),
        }
    }
    fn class_name(&self, i: u16) -> Result<&'a str> {
        match self.cp.get(i as usize) {
            Some(Cp::Class(name)) => self.utf(*name),
            _ => Err(reject("invalid CONSTANT_Class reference")),
        }
    }
    pub fn method_ref(&self, i: u16) -> Result<(&'a str, &'a str, &'a str)> {
        let Some(Cp::Method(class, pair)) = self.cp.get(i as usize) else {
            return Err(reject("invokestatic needs CONSTANT_Methodref"));
        };
        let Some(Cp::NameType(name, desc)) = self.cp.get(*pair as usize) else {
            return Err(reject("method reference has invalid NameAndType"));
        };
        Ok((self.class_name(*class)?, self.utf(*name)?, self.utf(*desc)?))
    }
    pub fn method(&self, name: &str, desc: &str, public: bool) -> Result<&Code<'a>> {
        let mut found = self
            .methods
            .iter()
            .filter(|m| m.name == name && m.desc == desc);
        let m = found
            .next()
            .ok_or_else(|| reject(format!("missing method {name}{desc}")))?;
        if found.next().is_some() {
            return Err(reject("duplicate method code"));
        }
        if m.flags & (0x0007 | 0x0008 | 0x0020 | 0x0100 | 0x0400) != (if public { 9 } else { 10 }) {
            return Err(unsupported(
                "method access, synchronization or implementation",
            ));
        }
        if m.handlers != 0 {
            return Err(unsupported("exception handlers on selected method"));
        }
        Ok(m)
    }
}
