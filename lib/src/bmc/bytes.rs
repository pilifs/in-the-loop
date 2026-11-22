//! Text as bytes and digits: `String.getBytes(UTF_8)`, `MessageDigest.isEqual`, `Arrays.copyOf` of an array of
//! primitives, `Integer.parseInt(String)` and the decimal digits a `StringBuilder` appends for an int.
//!
//! A password check turns a String into its bytes, a hash's text into numbers and bytes, and back, and compares
//! two encodings byte by byte (Spring Security's `BCrypt.checkpw`). Each of these is a formula over the cells the
//! engine holds, as the String methods are ([`super::strings`]): no path is split for what a call computes, only
//! for what it throws. Each is the JDK's method by its Javadoc and its source (JDK 25), and each is proved to be a
//! definition written out in Java, on every input of a bound, which is itself sampled against the JDK's method on
//! a JVM (`tests/fixtures/claims/claims/B.java` and `Samples.java`, run by `tests/claims.rs`).
//!
//! - `StandardCharsets.UTF_8` and `StandardCharsets.US_ASCII` (static fields of the JDK): each one object for the
//!   run, as it is one on a JVM. The other four are not read here.
//! - `String.getBytes(Charset)` with that object, on a String whose content the engine holds: the String's UTF-8
//!   encoding, as `String.encodeUTF8` writes it. A unit below `0x80` is one byte, one below `0x800` two, a high
//!   surrogate followed by a low one four for the pair, a surrogate that is in no such pair the one byte `?`
//!   (the encoder replaces, it does not throw), and any other unit three. The array is new, as long as the
//!   encoding, and has a cell for three times the String's cells. `NullPointerException` for a null charset; any
//!   other charset is the JDK call it was.
//! - `String.getBytes(Charset)` with `US_ASCII`: a unit below `0x80` is that byte, a high surrogate followed by a
//!   low one is the one byte `?` for the pair, and any other unit `?` (`String.encodeASCII`: the encoder replaces an
//!   unmappable character, a code point, by one `?`). The array is new, as long as the encoding.
//! - `String.getBytes(String)` with a constant name the JDK takes for UTF-8 (`UTF-8`, `UTF8` or `unicode-1-1-utf-8`,
//!   in any case of ASCII letters, as `Charset.forName` looks names up): the same encoding. `NullPointerException`
//!   for a null name; any other name is the JDK call it was, since a name the JDK has no charset for throws
//!   `UnsupportedEncodingException` and another charset encodes otherwise.
//! - `MessageDigest.isEqual(byte[], byte[])`: true for one array (two nulls included), false for one null, and
//!   otherwise whether the lengths are the same and every byte is. The JDK reads every byte whatever it finds, to
//!   take the same time; what it returns is this.
//! - `Arrays.copyOf(T[], int)` for `T` one of `boolean`, `byte`, `char`, `short`, `int` and `long`, and for an
//!   array of references: `NullPointerException` for null, `NegativeArraySizeException` for a negative length, and
//!   a new array of the original's class and of that length, with the original's elements up to the shorter of
//!   the two, zero (null) after them. The new array has a cell for each of the original's and for each further
//!   one the new length may ask for, as `newarray` counts them ([`Engine::new_array_cells`]).
//! - `Integer.parseInt(String)` and `Long.parseLong(String)`: an optional `+` or `-` and at least one digit, the value within the signed result width, or
//!   `NumberFormatException` (for null too). The JDK takes every Unicode decimal digit (`Character.digit`); the
//!   model takes `0` to `9`, and a String with a unit outside ASCII is the JDK call it was (a gap).
//! - the digits of an int, for `StringBuilder.append(int)` ([`Engine::decimal`]): `Integer.toString`'s, a `-` and
//!   the magnitude's decimal digits with no leading zero, `-2147483648` for the least.

use super::*;

/// The canonical ASCII fragment of the JDK basic decoder. Padding is optional
/// for a final group of two or three digits. Other inputs keep the JDK call boundary.
fn basic_base64_bytes(units: &[u16]) -> Option<Vec<u8>> {
    let digits = units.iter().position(|&c| c == u16::from(b'=')).unwrap_or(units.len());
    if !units[digits..].iter().all(|&c| c == u16::from(b'=')) ||
        !matches!((digits % 4, units.len() - digits), (0, 0) | (2, 0 | 2) | (3, 0 | 1)) { return None; }
    let mut decoded = Vec::with_capacity(digits * 3 / 4);
    let mut bits = 0u16;
    let mut count = 0;
    for &unit in &units[..digits] {
        let byte = u8::try_from(unit).ok()?;
        let value = match byte {
            b'A'..=b'Z' => byte - b'A',
            b'a'..=b'z' => byte - b'a' + 26,
            b'0'..=b'9' => byte - b'0' + 52,
            b'+' => 62,
            b'/' => 63,
            _ => return None,
        };
        bits = (bits << 6) | u16::from(value);
        count += 6;
        if count >= 8 {
            count -= 8;
            decoded.push((bits >> count) as u8);
            bits &= (1 << count) - 1;
        }
    }
    (bits == 0).then_some(decoded)
}

fn basic_base64_units(bytes: &[u8]) -> Vec<u16> {
    const ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut result = Vec::with_capacity(bytes.len().div_ceil(3) * 4);
    for group in bytes.chunks(3) {
        let a = group[0];
        let b = group.get(1).copied().unwrap_or(0);
        let c = group.get(2).copied().unwrap_or(0);
        let digit = |index: u8| u16::from(ALPHABET[usize::from(index)]);
        result.push(digit(a >> 2));
        result.push(digit((a & 3) << 4 | b >> 4));
        result.push(if group.len() >= 2 { digit((b & 15) << 2 | c >> 6) } else { u16::from(b'=') });
        result.push(if group.len() == 3 { digit(c & 63) } else { u16::from(b'=') });
    }
    result
}

const INTEGER: &str = "java/lang/Integer";
const DIGEST: &str = "java/security/MessageDigest";
const ARRAYS: &str = "java/util/Arrays";
/// The class of `StandardCharsets.UTF_8`'s object.
pub const CHARSET: &str = "java/nio/charset/Charset";
pub const STANDARD_CHARSETS: &str = "java/nio/charset/StandardCharsets";

/// The charset `StandardCharsets.name` is, where the engine holds it as one object ([`Literal::Charset`]).
pub fn charset_constant(owner: &str, name: &str) -> Option<&'static str> {
    match (owner, name) {
        (STANDARD_CHARSETS, "UTF_8") => Some("UTF_8"),
        (STANDARD_CHARSETS, "US_ASCII") => Some("US_ASCII"),
        (STANDARD_CHARSETS, "UTF_16BE") => Some("UTF_16BE"),
        (STANDARD_CHARSETS, "UTF_16LE") => Some("UTF_16LE"),
        _ => None,
    }
}

/// Whether the engine models the static call here.
pub fn models_static(owner: &str, name: &str, descriptor: &str) -> bool {
    matches!(
        (owner, name, descriptor),
        ("java/lang/String", "valueOf", "(C)Ljava/lang/String;") |
        (INTEGER, "parseInt", "(Ljava/lang/String;)I") | ("java/lang/Long", "parseLong", "(Ljava/lang/String;)J") | ("java/lang/Long", "toString", "(J)Ljava/lang/String;") |
        (DIGEST, "isEqual", "([B[B)Z") | (ARRAYS, "equals", "([B[B)Z") |
        (ARRAYS, "copyOf", "([ZI)[Z" | "([BI)[B" | "([CI)[C" | "([SI)[S" | "([II)[I" | "([JI)[J" | "([Ljava/lang/Object;I)[Ljava/lang/Object;")
    )
}

/// Whether the engine models `String.name(descriptor)` here.
pub fn models_string(name: &str, descriptor: &str) -> bool {
    matches!((name, descriptor), ("getBytes", "(Ljava/nio/charset/Charset;)[B" | "(Ljava/lang/String;)[B"))
}

/// The names `Charset.forName` takes for UTF-8 (`sun.nio.cs.UTF_8`'s and its aliases), compared as it compares
/// them, ignoring the case of ASCII letters.
const UTF8_NAMES: [&str; 3] = ["UTF-8", "UTF8", "unicode-1-1-utf-8"];

fn names_utf8(units: &[u16]) -> bool {
    let lower: Vec<u16> = units.iter().map(|&u| if (0x41..=0x5A).contains(&u) { u + 0x20 } else { u }).collect();
    UTF8_NAMES.iter().any(|name| name.to_ascii_lowercase().encode_utf16().eq(lower.iter().copied()))
}

/// A slice of a well-formed UTF-8 stream can start inside one character and
/// end inside another. OpenJDK replaces each stray continuation at the front
/// and the one incomplete scalar at the end. Interior malformed sequences
/// outside this language retain the original unsupported-operation diagnostic.
pub fn utf8_slice_units(bytes: &[u8]) -> Option<Vec<u16>> {
    let leading = bytes.iter().take_while(|&&b| (0x80..0xc0).contains(&b)).count();
    let mut units = vec![0xfffd; leading];
    let tail = &bytes[leading..];
    match std::str::from_utf8(tail) {
        Ok(text) => units.extend(text.encode_utf16()),
        Err(error) if error.error_len().is_none() => {
            units.extend(std::str::from_utf8(&tail[..error.valid_up_to()]).ok()?.encode_utf16());
            units.push(0xfffd);
        }
        Err(_) => return None,
    }
    Some(units)
}

impl Engine<'_> {
    /// The source array or String must be concrete and the receiver must be the
    /// original JDK basic codec. Both operations allocate a fresh result even for empty input.
    pub(super) fn basic_base64_call(&mut self, path: &mut Path, receiver: usize, member: &crate::classfile::MemberRef, args: &[Val]) -> Option<Step> {
        let [Val::R(Some(input))] = args else { return None };
        let result = match (member.owner.as_str(), member.name.as_str(), member.descriptor.as_str()) {
            ("java/util/Base64$Decoder", "decode", "(Ljava/lang/String;)[B")
                if path.literals.get(&Literal::BasicBase64Decoder) == Some(&receiver) => {
                let bytes = basic_base64_bytes(&self.constant_units(path, *input)?)?;
                let length = self.b.constant(bytes.len() as i64, 32);
                if let Err(stop) = self.new_array_cells(path, &length) { return Some(Err(stop)); }
                let cells = bytes.into_iter().map(|v| self.b.constant(i64::from(v), 8)).collect();
                let object = path.objects.len();
                path.objects.push(Obj { array: Some(Array { element: Type::Byte, length, cells, refs: Vec::new() }), ..Obj::new("[B") });
                object
            }
            ("java/util/Base64$Encoder", "encodeToString", "([B)Ljava/lang/String;")
                if path.literals.get(&Literal::BasicBase64Encoder) == Some(&receiver) => {
                if self.there_before(path, *input) {
                    if let Err(stop) = self.reads(path, || "reads the original byte array for Base64.encodeToString".into()) {
                        return Some(Err(stop));
                    }
                }
                let array = path.objects[*input].array.as_ref()?;
                if array.element != Type::Byte { return None; }
                let n = usize::try_from(self.b.constant_value(&array.length)?).ok()?;
                let bytes = array.cells.get(..n)?.iter().map(|b| self.b.constant_value(b).map(|v| v as u8)).collect::<Option<Vec<_>>>()?;
                self.string(path, &basic_base64_units(&bytes))
            }
            _ => return None,
        };
        self.push(path, Val::R(Some(result)));
        self.advance(path);
        Some(Ok(None))
    }

    /// Constant-fold a known byte slice and exact standard charset. All bounds,
    /// pre-existing heap reads and freshness checks precede the content update.
    pub(super) fn string_from_utf8(&mut self, path: &mut Path, object: usize, args: &[Val]) -> Option<Step> {
        let (source, range, charset) = match args {
            [Val::R(Some(a)), Val::R(Some(c))] => (*a, None, *c),
            [Val::R(Some(a)), Val::I(off), Val::I(len), Val::R(Some(c))] => (*a, Some((off, len)), *c),
            _ => return None,
        };
        if path.literals.get(&Literal::Charset("UTF_8")) != Some(&charset) { return None; }
        let array = path.objects[source].as_array().filter(|a| a.element == Type::Byte)?;
        let length = usize::try_from(self.b.constant_value(&array.length)?).ok()?;
        let (start, size) = match range {
            None => (0, length),
            Some((off, n)) => (usize::try_from(self.b.constant_value(off)?).ok()?, usize::try_from(self.b.constant_value(n)?).ok()?),
        };
        let end = start.checked_add(size)?;
        if end > length { return None; }
        let bytes: Vec<u8> = array.cells.get(start..end)?.iter().map(|b| self.b.constant_value(b).map(|n| n as u8)).collect::<Option<_>>()?;
        let units = utf8_slice_units(&bytes)?;
        if size > 0 && self.there_before(path, source) {
            if let Err(stop) = self.reads(path, || "String reads a pre-existing UTF-8 byte slice".into()) { return Some(Err(stop)); }
        }
        if let Err(stop) = self.keeps(path, Some(object), "initializes a pre-existing String") { return Some(Err(stop)); }
        let length = self.b.constant(units.len() as i64, 32);
        let cells = units.into_iter().map(|c| self.b.constant(i64::from(c), 16)).collect();
        path.objects[object].array = Some(Array { element: Type::Char, length, cells, refs: Vec::new() });
        self.advance(path);
        Some(Ok(None))
    }
    /// `String.getBytes(Charset)` and `String.getBytes(String)` on a String of content `s`: see the module's notes.
    /// `None` where the call stays the JDK's.
    pub(super) fn string_bytes(&mut self, path: &mut Path, s: &Array, descriptor: &str, args: &[Val]) -> Option<Step> {
        let [Val::R(charset)] = args else { return None };
        let Some(charset) = *charset else { return Some(self.raise(path, "java/lang/NullPointerException")) };
        let utf8 = if descriptor == "(Ljava/lang/String;)[B" {
            self.constant_units(path, charset).is_some_and(|units| names_utf8(&units))
        } else {
            path.literals.get(&Literal::Charset("UTF_8")) == Some(&charset)
        };
        let ascii = descriptor != "(Ljava/lang/String;)[B" && path.literals.get(&Literal::Charset("US_ASCII")) == Some(&charset);
        if !utf8 && !ascii {
            return None;
        }
        let (length, cells) = if ascii { self.ascii(s) } else { self.utf8(s) };
        path.objects.push(Obj { array: Some(Array { element: Type::Byte, length, cells, refs: Vec::new() }), ..Obj::new("[B") });
        let o = path.objects.len() - 1;
        self.push(path, Val::R(Some(o)));
        self.advance(path);
        Some(Ok(None))
    }

    /// The US-ASCII encoding of the String content `s`, as the JDK writes it: its length and its bytes, a cell for
    /// every byte it may have (one per unit).
    fn ascii(&mut self, s: &Array) -> (Bits, Vec<Bits>) {
        let n = s.cells.len();
        let constant16 = |engine: &mut Self, v: i64| engine.b.constant(v, 16);
        let x80 = constant16(self, 0x80);
        let (mask, high, low) = (constant16(self, 0xFC00), constant16(self, 0xD800), constant16(self, 0xDC00));
        let question = self.b.constant(i64::from(b'?'), 8);
        let inside: Vec<Lit> = (0..n)
            .map(|i| {
                let here = self.b.constant(i as i64, 32);
                self.b.slt(&here, &s.length)
            })
            .collect();
        let kind = |engine: &mut Self, cell: &Bits, of: &Bits| {
            let top = engine.b.and_bits(cell, &mask);
            engine.b.eq(&top, of)
        };
        let highs: Vec<Lit> = s.cells.iter().map(|c| kind(self, c, &high)).collect();
        let lows: Vec<Lit> = s.cells.iter().map(|c| kind(self, c, &low)).collect();
        // `second[i]`: the unit is the low surrogate of a pair, which the `?` of the unit before it stands for.
        let second: Vec<Lit> = (0..n).map(|i| if i == 0 { FALSE } else { self.b.all(&[lows[i], highs[i - 1], inside[i]]) }).collect();
        let mut position = self.b.constant(0, 32);
        let mut written: Vec<Vec<(Lit, Bits)>> = vec![Vec::new(); n];
        let one = self.b.constant(1, 32);
        for i in 0..n {
            let cell = &s.cells[i];
            let below = self.b.ult(cell, &x80);
            let byte = self.b.ite_bits(below, &cell[..8].to_vec(), &question);
            let writes = self.b.and(inside[i], -second[i]);
            if writes == FALSE {
                continue;
            }
            for start in 0..=i {
                let here = self.b.constant(start as i64, 32);
                let starts = self.b.eq(&position, &here);
                let at = self.b.and(writes, starts);
                if at != FALSE {
                    written[start].push((at, byte.clone()));
                }
            }
            let zero = self.b.constant(0, 32);
            let count = self.b.ite_bits(writes, &one, &zero);
            position = self.b.add(&position, &count);
        }
        let cells = written
            .into_iter()
            .map(|writers| {
                let mut value = self.b.constant(0, 8);
                for (at, byte) in writers {
                    value = self.b.ite_bits(at, &byte, &value);
                }
                value
            })
            .collect();
        (position, cells)
    }

    /// The UTF-8 encoding of the String content `s`, as the JDK writes it: its length and its bytes, a cell for
    /// every byte it may have.
    fn utf8(&mut self, s: &Array) -> (Bits, Vec<Bits>) {
        let n = s.cells.len();
        let constant16 = |engine: &mut Self, v: i64| engine.b.constant(v, 16);
        let (x80, x800) = (constant16(self, 0x80), constant16(self, 0x800));
        let (mask, high, low) = (constant16(self, 0xFC00), constant16(self, 0xD800), constant16(self, 0xDC00));
        let inside: Vec<Lit> = (0..n)
            .map(|i| {
                let here = self.b.constant(i as i64, 32);
                self.b.slt(&here, &s.length)
            })
            .collect();
        let kind = |engine: &mut Self, cell: &Bits, of: &Bits| {
            let top = engine.b.and_bits(cell, &mask);
            engine.b.eq(&top, of)
        };
        let highs: Vec<Lit> = s.cells.iter().map(|c| kind(self, c, &high)).collect();
        let lows: Vec<Lit> = s.cells.iter().map(|c| kind(self, c, &low)).collect();
        // `second[i]`: the unit is the low surrogate of a pair, written with the unit before it. A high surrogate
        // before it is the first of the pair whatever is before that one, since a high surrogate is no low one.
        let second: Vec<Lit> = (0..n).map(|i| if i == 0 { FALSE } else { self.b.all(&[lows[i], highs[i - 1], inside[i]]) }).collect();
        let mut position = self.b.constant(0, 32);
        // For each byte the encoding may have, the units that may write it: where each starts and what it writes.
        let mut written: Vec<Vec<(Lit, Bits)>> = vec![Vec::new(); 3 * n];
        for i in 0..n {
            let cell = &s.cells[i];
            let one = self.b.ult(cell, &x80);
            let below_800 = self.b.ult(cell, &x800);
            let two = self.b.and(-one, below_800);
            let first = if i + 1 < n { self.b.and(highs[i], second[i + 1]) } else { FALSE };
            let surrogate = self.b.or(highs[i], lows[i]);
            let alone = self.b.all(&[surrogate, -first, -second[i]]);
            let three = self.b.all(&[-below_800, -surrogate]);
            // The code point of a pair: 0x10000 + ((high - 0xD800) << 10) + (low - 0xDC00), 21 bits.
            let point: Bits = if i + 1 < n {
                let low_bits = &s.cells[i + 1][..10];
                let high_bits = &cell[..10];
                let joined: Bits = low_bits.iter().chain(high_bits.iter()).copied().chain(std::iter::once(FALSE)).collect();
                let base = self.b.constant(0x10000, 21);
                self.b.add(&joined, &base)
            } else {
                self.b.constant(0, 21)
            };
            let byte = |bits: &[Lit], lead: &[bool]| -> Bits { bits.iter().copied().chain(lead.iter().map(|&b| if b { TRUE } else { FALSE })).collect() };
            // The bytes of each form, most significant first; a continuation byte is 10 and six bits.
            let cont = |bits: &[Lit]| byte(bits, &[false, true]);
            let forms: [(Lit, Vec<Bits>); 5] = [
                (one, vec![cell[..8].to_vec()]),
                (two, vec![byte(&cell[6..11], &[false, true, true]), cont(&cell[..6])]),
                (three, vec![byte(&cell[12..16], &[false, true, true, true]), cont(&cell[6..12]), cont(&cell[..6])]),
                (first, vec![byte(&point[18..21], &[false, true, true, true, true]), cont(&point[12..18]), cont(&point[6..12]), cont(&point[..6])]),
                (alone, vec![self.b.constant(i64::from(b'?'), 8)]),
            ];
            let mut count = self.b.constant(0, 32);
            // The bytes before this unit are at least as many as the units (a pair's two units are four bytes) less
            // one, and at most three for each.
            let (least, most) = (i.saturating_sub(1), 3 * i);
            for (is, bytes) in &forms {
                let writes = self.b.and(inside[i], *is);
                if writes == FALSE {
                    continue;
                }
                let size = self.b.constant(bytes.len() as i64, 32);
                count = self.b.ite_bits(writes, &size, &count);
                for start in least..=most.min(3 * n - 1) {
                    let here = self.b.constant(start as i64, 32);
                    let starts = self.b.eq(&position, &here);
                    let at = self.b.and(writes, starts);
                    if at == FALSE {
                        continue;
                    }
                    for (k, value) in bytes.iter().enumerate() {
                        if start + k < 3 * n {
                            written[start + k].push((at, value.clone()));
                        }
                    }
                }
            }
            position = self.b.add(&position, &count);
        }
        let cells = written
            .into_iter()
            .map(|writers| {
                let mut value = self.b.constant(0, 8);
                for (at, byte) in writers {
                    value = self.b.ite_bits(at, &byte, &value);
                }
                value
            })
            .collect();
        (position, cells)
    }

    /// `Integer.parseInt`, `MessageDigest.isEqual` and `Arrays.copyOf`: see the module's notes. `None` where the
    /// call stays the JDK's.
    pub(super) fn bytes_static(&mut self, path: &mut Path, owner: &str, name: &str, descriptor: &str, args: &[Val]) -> Option<Step> {
        match (owner, name, args) {
            ("java/lang/String", "valueOf", [Val::I(unit)]) if descriptor == "(C)Ljava/lang/String;" && self.cp.fresh_string_factory(owner, name, descriptor) => {
                let text = self.new_string(path, self.b.constant(1, 32), vec![self.b.trunc(unit, 16)], Vec::new());
                self.push(path, Val::R(Some(text)));
                self.advance(path);
                Some(Ok(None))
            }
            ("java/lang/Long", "toString", [Val::J(word)]) if self.cp.fresh_string_factory(owner, name, descriptor) => {
                let (length, cells) = self.decimal(word);
                let text = self.new_string(path, length, cells, Vec::new());
                self.push(path, Val::R(Some(text)));
                self.advance(path);
                Some(Ok(None))
            }
            (INTEGER, "parseInt", [Val::R(text)]) | ("java/lang/Long", "parseLong", [Val::R(text)]) => {
                let Some(text) = *text else { return Some(self.raise(path, "java/lang/NumberFormatException")) };
                let s = path.objects[text].content().cloned()?;
                let wide = owner == "java/lang/Long";
                let (value, bad, beyond_ascii) = self.parsed_decimal(&s, if wide { 64 } else { 32 });
                let value = if wide { Val::J(value) } else { Val::I(value) };
                // On the side that is ASCII the call throws or returns; neither ends a path here.
                let mut inner: Step = Ok(None);
                let outer = self.branch_gap_or(path, beyond_ascii, (GapKind::JdkStaticMethod, owner, name, descriptor), |engine, side| {
                    inner = engine.branch_throw(side, bad, "java/lang/NumberFormatException", value);
                });
                Some(inner.and(outer))
            }
            (DIGEST, "isEqual", [Val::R(a), Val::R(b)]) | (ARRAYS, "equals", [Val::R(a), Val::R(b)]) => {
                let truth = match (*a, *b) {
                    (None, None) => TRUE,
                    (None, _) | (_, None) => FALSE,
                    (Some(a), Some(b)) if a == b => TRUE,
                    (Some(a), Some(b)) => {
                        if self.there_before(path, a) || self.there_before(path, b) {
                            if let Err(stop) = self.reads(path, || format!("reads an array that was there before the call ({name})")) {
                                return Some(Err(stop));
                            }
                        }
                        let (x, y) = (path.objects[a].as_array()?, path.objects[b].as_array()?);
                        if x.element != Type::Byte || y.element != Type::Byte { return None; }
                        let mut same = vec![self.b.eq(&x.length, &y.length)];
                        // Each backing vector covers every legal index. If lengths are equal,
                        // only the common capacity can contain an observable byte.
                        for (i, (left, right)) in x.cells.iter().zip(&y.cells).enumerate() {
                            let here = self.b.constant(i as i64, 32);
                            let inside = self.b.slt(&here, &x.length);
                            let equal = self.b.eq(left, right);
                            same.push(self.b.or(-inside, equal));
                        }
                        self.b.all(&same)
                    }
                };
                self.push_truth(path, truth);
                Some(Ok(None))
            }
            (ARRAYS, "copyOf", [Val::R(original), Val::I(length)]) => {
                let Some(original) = *original else { return Some(self.raise(path, "java/lang/NullPointerException")) };
                if path.objects[original].given {
                    if let Err(stop) = self.reads(path, || "reads an array that was there before the call (copyOf)".into()) {
                        return Some(Err(stop));
                    }
                }
                let from = path.objects[original].as_array()?.clone();
                let class = path.objects[original].class.clone();
                let negative = self.b.negative(length);
                // A cell for every element the new length may ask for: the original's where the solver shows it no
                // longer, else as many as a new array of that length has.
                let held = from.cells.len().max(from.refs.len());
                let longer = self.b.slt(&from.length, length);
                let mut assumptions = path.cond.clone();
                assumptions.push(longer);
                let cells = match self.solve(&assumptions) {
                    Ok(false) => held,
                    Ok(true) => {
                        let most = self.b.constant(held as i64 + 1, 32);
                        let beyond = self.b.slt(&most, length);
                        assumptions.pop();
                        assumptions.push(beyond);
                        match self.solve(&assumptions) {
                            Ok(false) => held + 1,
                            Ok(true) => match self.new_array_cells(path, length) {
                                Ok(cells) => cells,
                                Err(stop) => return Some(Err(stop)),
                            },
                            Err(stop) => return Some(Err(stop)),
                        }
                    }
                    Err(stop) => return Some(Err(stop)),
                };
                // Each cell is the original's where the original has an element there, and zero or null past it.
                let inside: Vec<Lit> = (0..cells)
                    .map(|i| {
                        let here = self.b.constant(i as i64, 32);
                        self.b.slt(&here, &from.length)
                    })
                    .collect();
                let (mut copied, mut references) = (Vec::new(), Vec::new());
                if holds_references(&from.element) {
                    for (i, inside) in inside.into_iter().enumerate() {
                        references.push(match from.refs.get(i) {
                            Some(cell) => choose(&mut self.b, inside, cell, &Val::R(None))?,
                            None => Val::R(None),
                        });
                    }
                } else {
                    let zero = self.b.constant(0, cell_width(&from.element));
                    for (i, inside) in inside.into_iter().enumerate() {
                        copied.push(match from.cells.get(i) {
                            Some(cell) => self.b.ite_bits(inside, cell, &zero),
                            None => zero.clone(),
                        });
                    }
                }
                let length = length.clone();
                Some(self.branch_throw_or(path, negative, "java/lang/NegativeArraySizeException", move |engine, path| {
                    path.objects.push(Obj { array: Some(Array { element: from.element, length, cells: copied, refs: references }), ..Obj::new(&class) });
                    let o = path.objects.len() - 1;
                    engine.push(path, Val::R(Some(o)));
                    engine.advance(path);
                }))
            }
            _ => None,
        }
    }

    /// Decimal int or long: the signed value, whether it throws instead, and whether a unit
    /// of `s` is outside ASCII, where the model does not say.
    fn parsed_decimal(&mut self, s: &Array, width: usize) -> (Bits, Lit, Lit) {
        let unit = |engine: &mut Self, c: u8| engine.b.constant(i64::from(c), 16);
        let (minus, plus, zero_digit, nine, ascii) = (unit(self, b'-'), unit(self, b'+'), unit(self, b'0'), unit(self, b'9'), self.b.constant(0x80, 16));
        let zero = self.b.constant(0, 32);
        let empty = self.b.eq(&s.length, &zero);
        let (negative, signed) = match s.cells.first() {
            Some(first) => {
                let negative = self.b.eq(first, &minus);
                let positive = self.b.eq(first, &plus);
                (negative, self.b.or(negative, positive))
            }
            None => (FALSE, FALSE),
        };
        let one = self.b.constant(1, 32);
        let only_sign = {
            let is_one = self.b.eq(&s.length, &one);
            self.b.and(signed, is_one)
        };
        let mut bad = vec![empty, only_sign];
        let mut outside = Vec::new();
        let ten = self.b.constant(10, width);
        let max = if width == 64 { i64::MAX } else { i64::from(i32::MAX) };
        let cutoff = self.b.constant(max / 10, width);
        // Both signed widths end in 7 for MAX and 8 for the magnitude of MIN.
        let last = self.b.ite_bits(negative, &self.b.constant(8, width), &self.b.constant(7, width));
        let mut value = self.b.constant(0, width);
        for (i, cell) in s.cells.iter().enumerate() {
            let here = self.b.constant(i as i64, 32);
            let inside = self.b.slt(&here, &s.length);
            let beyond = self.b.ult(cell, &ascii);
            outside.push(self.b.and(inside, -beyond));
            let read = if i == 0 { self.b.and(inside, -signed) } else { inside };
            let below = self.b.ult(cell, &zero_digit);
            let above = self.b.ult(&nine, cell);
            let digit = self.b.and(-below, -above);
            bad.push(self.b.and(read, -digit));
            // Test before multiplying so even a value that wraps around more than once stays invalid.
            let digit_value = self.b.zext(&cell[..4].to_vec(), width);
            let above = self.b.ult(&cutoff, &value);
            let at_limit = self.b.eq(&value, &cutoff);
            let last_over = self.b.ult(&last, &digit_value);
            let overflow_at_limit = self.b.and(at_limit, last_over);
            let overflow = self.b.or(above, overflow_at_limit);
            bad.push(self.b.and(read, overflow));
            let times = self.b.mul(&value, &ten);
            let next = self.b.add(&times, &digit_value);
            value = self.b.ite_bits(read, &next, &value);
        }
        let negated = self.b.neg(&value);
        let result = self.b.ite_bits(negative, &negated, &value);
        (result, self.any(&bad), self.any(&outside))
    }

    /// Signed decimal UTF-16 units of an int or long, including the minimum value of each type.
    pub(super) fn decimal(&mut self, value: &Bits) -> (Bits, Vec<Bits>) {
        if let Some(n) = self.b.constant_value(value) {
            let text = n.to_string();
            return (self.b.constant(text.len() as i64, 32), text.bytes().map(|ch| self.b.constant(i64::from(ch), 16)).collect());
        }
        let width = if value.len() == 64 { 64 } else { 34 };
        let digits_in_type = if value.len() == 64 { 19 } else { 10 };
        let negative = self.b.negative(value);
        let wide = self.b.sext(value, width);
        let negated = self.b.neg(&wide);
        let magnitude = self.b.ite_bits(negative, &negated, &wide);
        // The digits from the least: the magnitude's remainders by ten, and how many it has.
        let ten = self.b.constant(10, width);
        let mut rest = magnitude;
        let mut digits: Vec<Bits> = Vec::with_capacity(digits_in_type);
        let mut more: Vec<Lit> = Vec::with_capacity(digits_in_type);
        for _ in 0..digits_in_type {
            let (quotient, remainder) = self.b.udivrem(&rest, &ten);
            let digit: Bits = remainder[..4].iter().copied().chain(std::iter::repeat(FALSE)).take(16).collect();
            let character = self.b.constant(i64::from(b'0'), 16);
            digits.push(self.b.add(&digit, &character));
            let none = self.b.is_zero(&quotient);
            more.push(-none);
            rest = quotient;
        }
        // `count`: the digits, at least one.
        let mut count = self.b.constant(1, 32);
        for (k, &has) in more.iter().enumerate().take(digits_in_type - 1) {
            let this = self.b.constant(k as i64 + 2, 32);
            count = self.b.ite_bits(has, &this, &count);
        }
        let one = self.b.constant(1, 32);
        let with_sign = self.b.add(&count, &one);
        let length = self.b.ite_bits(negative, &with_sign, &count);
        // The unit at `i`: the sign first, then the digits from the most significant.
        let minus = self.b.constant(i64::from(b'-'), 16);
        let cells = (0..=digits_in_type)
            .map(|i| {
                let mut unit = self.b.constant(0, 16);
                for (k, digit) in digits.iter().enumerate() {
                    // Digit `k` (from the least) is at `length - 1 - k`.
                    let offset = self.b.constant(i as i64 + 1 + k as i64, 32);
                    let here = self.b.eq(&length, &offset);
                    unit = self.b.ite_bits(here, digit, &unit);
                }
                if i == 0 {
                    unit = self.b.ite_bits(negative, &minus, &unit);
                }
                unit
            })
            .collect();
        (length, cells)
    }
}
