//! `java.lang.String` beyond its first six methods, and `java.lang.StringBuilder`, on content.
//!
//! A String the engine holds the content of is a length and a cell per code unit ([`super::Obj::content`]); the
//! methods here are formulas over those, as the first six are (`length`, `isEmpty`, `charAt`, `equals`,
//! `hashCode`, `startsWith`, in [`super::Engine::string_method`]): no path is split for what a method computes,
//! only for what it throws. Each is the JDK's method by its Javadoc and its source (JDK 25), sampled against a JVM
//! by the values corpus (`values::OPERATIONS`).
//!
//! - `substring(int)`, `substring(int, int)`: `StringIndexOutOfBoundsException` for a begin below zero, an end
//!   beyond the length or before the begin; the units between. The JDK returns the String itself for its whole
//!   range and the literal `""` for an empty one, and so does this: the new String is those objects where the
//!   range is ([`super::Obj::same`]), which `==` sees and nothing else does.
//! - `indexOf(int)`, `indexOf(int, int)`: the first index at or after the start (below zero is zero) whose unit is
//!   the character, or whose two units are the surrogate pair of a supplementary one; `-1` for none, and for a
//!   value that is no code point.
//! - `lastIndexOf(int)`: the same test at every index, the last one that meets it.
//! - `indexOf(String)`, `indexOf(String, int)`: `NullPointerException` for null; the first index at or after the
//!   start (held to the length) where the other's units all are; the start itself for the empty String.
//! - `endsWith(String)`: `NullPointerException` for null; the other's units at the end.
//! - `toLowerCase()` and `toLowerCase(Locale)`: of a String whose units are all ASCII, each of `A` to `Z` lowered,
//!   and the String itself when none is. Under a Turkish or an Azeri locale `I` is lowered to U+0131, the dotless
//!   i, and under every other, Lithuanian included, an ASCII String is lowered alike ([`super::locale`]). The
//!   locale is the one given, or the default the path set last (`Locale.setDefault`); where the path set none it is
//!   the JVM's own, which the run assumes is none of Turkish, Azeri and Lithuanian and says so
//!   ([`LOCALE_ASSUMPTION`]). A String with a unit outside ASCII is lowered by Unicode's tables, its context (a
//!   final sigma) and the locale's rules, which the engine has not: there the call is the gap it was, as it is
//!   under a Locale the engine knows nothing of.
//!
//! `Character.isLetter(char)` of a unit below 128 is whether it is one of ASCII's 52 letters, as a formula; of any
//! other unit it is the JDK's table's to say, and the call is the gap it was.
//!
//! A `StringBuilder` is an object with a content of its own, which its methods change: `StringBuilder()`,
//! `StringBuilder(int)` of a constant capacity from 0 to [`MOST_BUILDER_CONTENT`] (empty; another capacity is the
//! JDK call), `StringBuilder(String)` (`NullPointerException` for null), `length()`, `charAt(int)`
//! (`StringIndexOutOfBoundsException` outside the length), `append(String)` (the four units `null` for null),
//! `append(Object)` (`null` for null, a String's units, an exception's `toString()` where the engine has it,
//! [`super::throwables`], and the JDK call for any other object),
//! `appendCodePoint(int)` (one BMP code unit or a surrogate pair, with an invalid int throwing before any write),
//! `append(char)`, `append(int)` (the int's decimal digits, [`super::bytes`]; each the builder itself returned, its
//! content at most [`MOST_BUILDER_CONTENT`] units, past which the run ends with no verdict), `indexOf(String)`,
//! `indexOf(String, int)`, `substring(int, int)` (the literal `""` for an empty range, else a new String), `delete(int, int)` (the
//! end held to the length; `StringIndexOutOfBoundsException` for a start below zero or beyond the end; the builder
//! itself returned) and `toString()` (the literal `""` when empty, else a new String). Any other method of a
//! builder is the JDK call it was, a gap: after it the engine holds the builder's content no longer, whatever the
//! gap's assumption or contract says the call did, and a later modelled call on that builder that reads its content
//! out is refused by name; an `append` or a `charAt` on it is the JDK call again, a gap as it was before the engine
//! modelled it. A contract given for a modelled call stands in place of the model ([`gaps::modelled_jdk_call`]).

use super::*;

/// The builder's class.
pub const BUILDER: &str = "java/lang/StringBuilder";

const CHARACTER: &str = "java/lang/Character";

/// The most code units a builder the engine holds the content of has a cell for.
pub const MOST_BUILDER_CONTENT: usize = 1024;

/// What a run that lowered a String's case under the JVM's own default locale took for granted about it: a run
/// that set the default itself before it lowered anything assumes nothing ([`super::locale`]).
pub const LOCALE_ASSUMPTION: &str = "the default locale's language is not Turkish, Azeri or Lithuanian (tr, az, lt): String.toLowerCase() reads Locale.getDefault(), and only those three change how an ASCII letter is lowered";

/// Whether the engine models `String.name(descriptor)` here.
pub fn models(name: &str, descriptor: &str) -> bool {
    matches!(
        (name, descriptor),
        ("substring", "(I)Ljava/lang/String;" | "(II)Ljava/lang/String;") | ("indexOf", "(I)I" | "(II)I" | "(Ljava/lang/String;)I" | "(Ljava/lang/String;I)I") | ("lastIndexOf", "(I)I") | ("endsWith", "(Ljava/lang/String;)Z") | ("toLowerCase", "()Ljava/lang/String;")
    )
}

/// Character operations on a symbolic unit or code point.
pub fn models_static(owner: &str, name: &str, descriptor: &str) -> bool {
    owner == CHARACTER && matches!((name, descriptor), ("isLetter", "(C)Z") | ("toChars", "(I)[C"))
}

/// Whether the engine models `StringBuilder.name(descriptor)`, its two constructors included.
pub fn models_builder(owner: &str, name: &str, descriptor: &str) -> bool {
    owner == BUILDER
        && matches!(
            (name, descriptor),
            ("<init>", "()V" | "(I)V" | "(Ljava/lang/String;)V") | ("length", "()I") | ("charAt", "(I)C") | ("setCharAt", "(IC)V")
                | ("append", "(Ljava/lang/String;)Ljava/lang/StringBuilder;" | "(Ljava/lang/Object;)Ljava/lang/StringBuilder;" | "(C)Ljava/lang/StringBuilder;" | "(I)Ljava/lang/StringBuilder;" | "(J)Ljava/lang/StringBuilder;")
                | ("appendCodePoint", "(I)Ljava/lang/StringBuilder;") | ("indexOf", "(Ljava/lang/String;)I" | "(Ljava/lang/String;I)I") | ("substring", "(II)Ljava/lang/String;") | ("delete", "(II)Ljava/lang/StringBuilder;") | ("toString", "()Ljava/lang/String;")
        )
}

impl Engine<'_> {
    /// The unit of `s` at the index `at`: a choice among its cells, zero for an index it has no cell for.
    fn unit_at(&mut self, s: &Array, at: &Bits) -> Bits {
        let mut unit = self.b.constant(0, 16);
        for (i, cell) in s.cells.iter().enumerate().rev() {
            let here = self.b.constant(i as i64, 32);
            let is = self.b.eq(at, &here);
            unit = self.b.ite_bits(is, cell, &unit);
        }
        unit
    }

    /// A new String of `length` units, `cells`, which is the object `o` under each guard of `same`.
    pub(super) fn new_string(&mut self, path: &mut Path, length: Bits, cells: Vec<Bits>, same: Vec<(Lit, usize)>) -> usize {
        path.objects.push(Obj { array: Some(Array { element: Type::Char, length, cells, refs: Vec::new() }), same: same.into_iter().filter(|(g, _)| *g != FALSE).collect(), ..Obj::new(STRING) });
        path.objects.len() - 1
    }

    /// The units of `s` followed by those of `t`: the unit at `i` is `s`'s own below its length, and `t`'s at
    /// `i - length` from there.
    pub(super) fn joined(&mut self, s: &Array, t: &Array) -> Array {
        let length = self.b.add(&s.length, &t.length);
        let cells = (0..s.cells.len() + t.cells.len())
            .map(|i| {
                let here = self.b.constant(i as i64, 32);
                let own = self.b.slt(&here, &s.length);
                let at = self.b.sub(&here, &s.length);
                let other = self.unit_at(t, &at);
                match s.cells.get(i) {
                    Some(cell) => self.b.ite_bits(own, cell, &other),
                    None => other,
                }
            })
            .collect();
        Array { element: Type::Char, length, cells, refs: Vec::new() }
    }

    /// The literal `""`, which the JDK returns for an empty range.
    fn empty_literal(&mut self, path: &mut Path) -> usize {
        self.literal(path, Literal::Str(Vec::new()), STRING)
    }

    /// The units of `s` from `begin` to `end`, as a String: the JDK's `newString` of a checked range, which is the
    /// literal `""` when the range is empty; `itself` is the String the range is taken of, returned for its whole
    /// range, and absent for a builder's.
    pub(super) fn range(&mut self, path: &mut Path, s: &Array, begin: &Bits, end: &Bits, itself: Option<usize>) -> Val {
        let zero = self.b.constant(0, 32);
        let whole = match itself {
            Some(_) => {
                let from_start = self.b.eq(begin, &zero);
                let to_end = self.b.eq(end, &s.length);
                self.b.and(from_start, to_end)
            }
            None => FALSE,
        };
        if whole == TRUE {
            return Val::R(itself);
        }
        let none = self.b.eq(begin, end);
        let empty = self.b.and(-whole, none);
        // A begin that is a constant leaves the cells after it; any other, every cell.
        let skipped = self.b.constant_value(begin).and_then(|b| usize::try_from(b).ok()).unwrap_or(0).min(s.cells.len());
        let most = match self.b.constant_value(end).and_then(|e| usize::try_from(e).ok()) {
            Some(e) => e.min(s.cells.len()).saturating_sub(skipped),
            None => s.cells.len() - skipped,
        };
        let mut cells = Vec::with_capacity(most);
        for i in 0..most {
            let offset = self.b.constant(i as i64, 32);
            let at = self.b.add(begin, &offset);
            cells.push(self.unit_at(s, &at));
        }
        let length = self.b.sub(end, begin);
        let mut same = Vec::new();
        if let Some(o) = itself {
            same.push((whole, o));
        }
        if empty != FALSE {
            let literal = self.empty_literal(path);
            same.push((empty, literal));
        }
        Val::R(Some(self.new_string(path, length, cells, same)))
    }

    /// Whether `begin..end` is no range of a sequence of `length` units: the JDK's `checkBoundsBeginEnd`.
    fn bad_range(&mut self, begin: &Bits, end: &Bits, length: &Bits) -> Lit {
        let zero = self.b.constant(0, 32);
        let below = self.b.slt(begin, &zero);
        let crossed = self.b.slt(end, begin);
        let beyond = self.b.slt(length, end);
        let either = self.b.or(below, crossed);
        self.b.or(either, beyond)
    }

    /// The first index of `s` at or after `from` where the code point `ch` is: its unit, or the surrogate pair of
    /// a supplementary one; `-1` where there is none (`String.indexOf(int, int)`).
    fn index_of_unit(&mut self, s: &Array, ch: &Bits, from: &Bits) -> Bits {
        self.unit_hit(s, ch, from, false)
    }

    /// UTF-16 code units for a valid Java code point. An isolated surrogate in the BMP is one unit.
    fn code_point_units(&mut self, ch: &Bits) -> (Lit, Array) {
        let bmp_limit = self.b.constant(0x1_0000, 32);
        let limit = self.b.constant(0x11_0000, 32);
        let is_bmp = self.b.ult(ch, &bmp_limit);
        let below_limit = self.b.ult(ch, &limit);
        let unit = self.b.trunc(ch, 16);
        let one = self.b.constant(1, 32);
        if is_bmp == TRUE {
            return (below_limit, Array { element: Type::Char, length: one, cells: vec![unit], refs: Vec::new() });
        }
        let offset = self.b.sub(ch, &bmp_limit);
        let ten = self.b.constant(10, 32);
        let top = self.b.ushr(&offset, &ten);
        let high_base = self.b.constant(0xD800, 32);
        let high = self.b.add(&top, &high_base);
        let high = self.b.trunc(&high, 16);
        let mask = self.b.constant(0x3ff, 32);
        let bottom = self.b.and_bits(&offset, &mask);
        let low_base = self.b.constant(0xDC00, 32);
        let low = self.b.add(&bottom, &low_base);
        let low = self.b.trunc(&low, 16);
        let two = self.b.constant(2, 32);
        let length = self.b.ite_bits(is_bmp, &one, &two);
        let first = self.b.ite_bits(is_bmp, &unit, &high);
        (below_limit, Array { element: Type::Char, length, cells: vec![first, low], refs: Vec::new() })
    }

    fn unit_hit(&mut self, s: &Array, ch: &Bits, from: &Bits, last: bool) -> Bits {
        let (valid, encoded) = self.code_point_units(ch);
        let one_unit = self.b.constant(1, 32);
        let is_bmp = self.b.eq(&encoded.length, &one_unit);
        let is_supplementary = self.b.and(valid, -is_bmp);
        let mut result = self.b.constant(-1, 32);
        // Each hit overrides the ones met before it, so the order of the indices is which hit wins.
        let order: Vec<usize> = if last { (0..s.cells.len()).collect() } else { (0..s.cells.len()).rev().collect() };
        for i in order {
            let here = self.b.constant(i as i64, 32);
            let inside = self.b.slt(&here, &s.length);
            let after = self.b.sle(from, &here);
            let one = self.b.eq(&s.cells[i], &encoded.cells[0]);
            let one = self.b.and(is_bmp, one);
            let pair = match s.cells.get(i + 1).zip(encoded.cells.get(1)) {
                Some((next, low)) => {
                    let second = self.b.constant(i as i64 + 1, 32);
                    let has_second = self.b.slt(&second, &s.length);
                    let first_is = self.b.eq(&s.cells[i], &encoded.cells[0]);
                    let second_is = self.b.eq(next, low);
                    self.b.all(&[is_supplementary, has_second, first_is, second_is])
                }
                None => FALSE,
            };
            let found = self.b.or(one, pair);
            let hit = self.b.all(&[inside, after, found]);
            result = self.b.ite_bits(hit, &here, &result);
        }
        result
    }

    /// The first index of `s` at or after `from` (held to `0..=length`) where the units of `t` all are; `-1` where
    /// there is none (`String.indexOf(String, int)`: the empty String is found at the start index).
    fn index_of_string(&mut self, s: &Array, t: &Array, from: &Bits) -> Bits {
        let zero = self.b.constant(0, 32);
        let negative = self.b.slt(from, &zero);
        let start = self.b.ite_bits(negative, &zero, from);
        let beyond = self.b.slt(&s.length, &start);
        let start = self.b.ite_bits(beyond, &s.length, &start);
        let mut result = self.b.constant(-1, 32);
        for i in (0..=s.cells.len()).rev() {
            let here = self.b.constant(i as i64, 32);
            let end = self.b.add(&here, &t.length);
            let fits = self.b.sle(&end, &s.length);
            let after = self.b.sle(&start, &here);
            let mut agree = vec![fits, after];
            for (k, unit) in t.cells.iter().enumerate() {
                let index = self.b.constant(k as i64, 32);
                let inside = self.b.slt(&index, &t.length);
                let same = match s.cells.get(i + k) {
                    Some(cell) => self.b.eq(cell, unit),
                    None => FALSE,
                };
                agree.push(self.b.or(-inside, same));
            }
            let hit = self.b.all(&agree);
            result = self.b.ite_bits(hit, &here, &result);
        }
        result
    }

    /// Whether the unit is an ASCII upper-case letter, and the unit with such a letter lowered: one formula for
    /// `String.toLowerCase()` and for a comparison that ignores ASCII case ([`regex`]).
    pub(super) fn lowered_ascii(&mut self, unit: &Bits) -> (Lit, Bits) {
        let (upper_a, upper_z) = (self.b.constant(i64::from(b'A'), 16), self.b.constant(i64::from(b'Z'), 16));
        let below = self.b.ult(unit, &upper_a);
        let above = self.b.ult(&upper_z, unit);
        let is_upper = self.b.and(-below, -above);
        let case_bit = self.b.constant(0x20, 16);
        let lowered = self.b.or_bits(unit, &case_bit);
        (is_upper, self.b.ite_bits(is_upper, &lowered, unit))
    }

    /// `Character.isLetter(char)`: of an ASCII unit, whether it is one of the 52 letters of ASCII (the units below
    /// 128 whose general category is a letter's); of any other unit it is the JDK's table's to say, the gap the
    /// call was.
    pub(super) fn is_letter(&mut self, path: &mut Path, args: &[Val]) -> Step {
        let [Val::I(c)] = args else { return unsupported(format!("Character.isLetter with arguments {args:?}")) };
        let unit = self.b.trunc(c, 16);
        let lowered = self.lowered_ascii(&unit).1;
        let (a, z, limit) = (self.b.constant(i64::from(b'a'), 16), self.b.constant(i64::from(b'z'), 16), self.b.constant(128, 16));
        let below = self.b.ult(&lowered, &a);
        let above = self.b.ult(&z, &lowered);
        let letter = self.b.and(-below, -above);
        let ascii = self.b.ult(&unit, &limit);
        self.branch_gap_or(path, -ascii, (GapKind::JdkStaticMethod, CHARACTER, "isLetter", "(C)Z"), move |engine, path| engine.push_truth(path, letter))
    }

    pub(super) fn to_chars(&mut self, path: &mut Path, ch: &Bits) -> Step {
        let (valid, units) = self.code_point_units(ch);
        self.branch_throw_or(path, -valid, "java/lang/IllegalArgumentException", move |engine, path| {
            let array = engine.alloc(path, "[C");
            path.objects[array].array = Some(units);
            engine.push(path, Val::R(Some(array)));
            engine.advance(path);
        })
    }

    /// Pushes a truth value as the int the JVM holds it as.
    pub(super) fn push_truth(&mut self, path: &mut Path, truth: Lit) {
        let (one, zero) = (self.b.constant(1, 32), self.b.constant(0, 32));
        let value = self.b.ite_bits(truth, &one, &zero);
        self.push(path, Val::I(value));
        self.advance(path);
    }

    /// The content of the String argument `r`, a `NullPointerException` thrown where it is null: `Err` carries the
    /// step that ends the call (the exception, or a String with no content, whose call stays the JDK's).
    pub(super) fn string_argument(&mut self, path: &mut Path, r: Option<usize>, gap: (&str, &str, &str)) -> Result<Array, Step> {
        let Some(p) = r else { return Err(self.raise(path, "java/lang/NullPointerException")) };
        match path.objects[p].content().cloned() {
            Some(t) => Ok(t),
            None => match path.objects[p].limit.clone() {
                Some(why) => Err(unsupported(why)),
                None => Err(Ok(self.meet(path, GapKind::JdkPrimitiveMethod, gap.0, gap.1, gap.2))),
            },
        }
    }

    /// The String methods of this module on the String `o` of content `s`: see the module's notes.
    pub(super) fn string_method_on_content(&mut self, path: &mut Path, o: usize, s: &Array, name: &str, descriptor: &str, args: &[Val]) -> Step {
        match (name, descriptor, args) {
            ("substring", "(I)Ljava/lang/String;", [Val::I(begin)]) => {
                let length = s.length.clone();
                let bad = self.bad_range(begin, &length, &length);
                let value = self.range(path, s, begin, &length, Some(o));
                self.branch_throw(path, bad, "java/lang/StringIndexOutOfBoundsException", value)
            }
            ("substring", _, [Val::I(begin), Val::I(end)]) => {
                let bad = self.bad_range(begin, end, &s.length);
                let value = self.range(path, s, begin, end, Some(o));
                self.branch_throw(path, bad, "java/lang/StringIndexOutOfBoundsException", value)
            }
            ("indexOf", "(I)I", [Val::I(ch)]) => {
                let zero = self.b.constant(0, 32);
                let at = self.index_of_unit(s, ch, &zero);
                self.push(path, Val::I(at));
                self.advance(path);
                Ok(None)
            }
            ("lastIndexOf", "(I)I", [Val::I(ch)]) => {
                let zero = self.b.constant(0, 32);
                let at = self.unit_hit(s, ch, &zero, true);
                self.push(path, Val::I(at));
                self.advance(path);
                Ok(None)
            }
            ("indexOf", "(II)I", [Val::I(ch), Val::I(from)]) => {
                let at = self.index_of_unit(s, ch, from);
                self.push(path, Val::I(at));
                self.advance(path);
                Ok(None)
            }
            ("indexOf", _, [Val::R(other), rest @ ..]) => {
                let t = match self.string_argument(path, *other, (STRING, name, descriptor)) {
                    Ok(t) => t,
                    Err(step) => return step,
                };
                let from = match rest {
                    [Val::I(from)] => from.clone(),
                    _ => self.b.constant(0, 32),
                };
                let at = self.index_of_string(s, &t, &from);
                self.push(path, Val::I(at));
                self.advance(path);
                Ok(None)
            }
            ("endsWith", _, [Val::R(other)]) => {
                let t = match self.string_argument(path, *other, (STRING, name, descriptor)) {
                    Ok(t) => t,
                    Err(step) => return step,
                };
                let fits = self.b.sle(&t.length, &s.length);
                let offset = self.b.sub(&s.length, &t.length);
                let mut agree = vec![fits];
                for (k, unit) in t.cells.iter().enumerate() {
                    let index = self.b.constant(k as i64, 32);
                    let inside = self.b.slt(&index, &t.length);
                    let at = self.b.add(&offset, &index);
                    let mine = self.unit_at(s, &at);
                    let same = self.b.eq(&mine, unit);
                    agree.push(self.b.or(-inside, same));
                }
                let truth = self.b.all(&agree);
                self.push_truth(path, truth);
                Ok(None)
            }
            ("toLowerCase", _, [] | [Val::R(_)]) => {
                // The locale's one fact that matters to an ASCII String ([`locale`]): the default the path set, or
                // the argument's. A locale the engine knows nothing of leaves the call the JDK's.
                let dotless = match args {
                    [Val::R(None)] => return self.raise(path, "java/lang/NullPointerException"),
                    [Val::R(Some(given))] => self.argument_dotless(path, *given),
                    _ => {
                        self.reads(path, || "reads the default locale (toLowerCase())".into())?;
                        self.default_dotless(path)
                    }
                };
                let Some(dotless) = dotless else {
                    return match self.meet(path, GapKind::JdkReferenceMethod, STRING, name, descriptor) {
                        Some(end) => Ok(Some(end)),
                        None => {
                            let r = self.alloc(path, STRING);
                            self.push(path, Val::R(Some(r)));
                            self.advance(path);
                            Ok(None)
                        }
                    };
                };
                let (capital_i, dotless_i) = (self.b.constant(i64::from(b'I'), 16), self.b.constant(0x131, 16));
                let ascii_limit = self.b.constant(128, 16);
                let mut outside = Vec::new();
                let mut changes = Vec::new();
                let mut cells = Vec::with_capacity(s.cells.len());
                for (i, cell) in s.cells.iter().enumerate() {
                    let here = self.b.constant(i as i64, 32);
                    let inside = self.b.slt(&here, &s.length);
                    let ascii = self.b.ult(cell, &ascii_limit);
                    outside.push(self.b.and(inside, -ascii));
                    let (is_upper, lowered) = self.lowered_ascii(cell);
                    changes.push(self.b.and(inside, is_upper));
                    // Turkish and Azeri lower `I` to the dotless i; every other ASCII letter as any locale does.
                    let is_i = self.b.eq(cell, &capital_i);
                    let to_dotless = self.b.and(dotless, is_i);
                    cells.push(self.b.ite_bits(to_dotless, &dotless_i, &lowered));
                }
                let beyond_ascii = self.any(&outside);
                let changed = self.any(&changes);
                let (owner, name, descriptor) = (STRING, name.to_string(), descriptor.to_string());
                let length = s.length.clone();
                let original = s.clone();
                self.branch_gap_or(path, beyond_ascii, (GapKind::JdkReferenceMethod, owner, &name, &descriptor), move |engine, path| {
                    let value = if changed == FALSE {
                        o
                    } else {
                        // The new String remembers the units it is the lower case of ([`regex::Regex::Lowered`]).
                        let lowered = engine.new_string(path, length, cells, vec![(-changed, o)]);
                        // Its units are the original's with the ASCII capitals lowered only where no locale lowers
                        // `I` otherwise.
                        if dotless == FALSE {
                            path.objects[lowered].regex = Some(Rc::new(regex::Regex::lowered(&original)));
                        }
                        lowered
                    };
                    engine.push(path, Val::R(Some(value)));
                    engine.advance(path);
                })
            }
            _ => unsupported(format!("String.{name}{descriptor} with arguments {args:?}")),
        }
    }

    /// A `StringBuilder`'s constructor or method on the builder `o`: see the module's notes. `None` for a call
    /// the module doesn't model, which stays the JDK call it was.
    pub(super) fn builder_method(&mut self, path: &mut Path, o: usize, name: &str, descriptor: &str, args: &[Val]) -> Option<Step> {
        if path.objects[o].class != BUILDER || !models_builder(BUILDER, name, descriptor) {
            return None;
        }
        if !matches!(name, "length" | "charAt" | "indexOf" | "substring" | "toString") {
            if let Err(stop) = self.keeps(path, Some(o), "changes a StringBuilder made before it was called") {
                return Some(Err(stop));
            }
        }
        // A builder is no String: a caller can change one it holds (a final static field's, a lambda's captured
        // one) before it calls, so a lemma reads none that was there before the call ([`Engine::reads`]).
        if path.objects[o].given {
            if let Err(stop) = self.reads(path, || format!("reads a StringBuilder that was there before the call ({name})")) {
                return Some(Err(stop));
            }
        }
        let empty = |engine: &mut Self| Array { element: Type::Char, length: engine.b.constant(0, 32), cells: Vec::new(), refs: Vec::new() };
        if name == "<init>" {
            let content = match args {
                [] => empty(self),
                // A capacity is no content: of a constant from 0 to [`MOST_BUILDER_CONTENT`] the builder is empty. A
                // negative one throws and a huge one may run out of memory, which the engine leaves to the JDK.
                [Val::I(capacity)] => match self.b.constant_value(capacity) {
                    Some(c) if (0..=MOST_BUILDER_CONTENT as i64).contains(&(c as i32 as i64)) => empty(self),
                    _ => return None,
                },
                [Val::R(from)] => match self.string_argument(path, *from, (BUILDER, name, descriptor)) {
                    Ok(t) => t,
                    Err(step) => return Some(step),
                },
                _ => return Some(unsupported(format!("StringBuilder.{name}{descriptor} with arguments {args:?}"))),
            };
            path.objects[o].array = Some(content);
            self.advance(path);
            return Some(Ok(None));
        }
        // A builder made or changed by a call the module doesn't model (a gap, or a contract's call) has no content.
        // An `append` or a `charAt` there is the JDK call it is, a gap as any call of a builder with no model; a
        // method that reads the content out (`toString`, `length`, …) is refused by name, as it would give the
        // content the engine no longer holds.
        let Some(s) = path.objects[o].array.clone() else {
            if matches!(name, "append" | "appendCodePoint" | "charAt") {
                return None;
            }
            return Some(unsupported(format!("StringBuilder.{name} on a builder made or changed by a call the engine does not model")));
        };
        Some(match (name, args) {
            ("length", []) => {
                self.push(path, Val::I(s.length));
                self.advance(path);
                Ok(None)
            }
            ("charAt", [Val::I(index)]) => {
                // An int compared unsigned: a negative index is out of bounds too (`Preconditions.checkIndex`).
                let inside = self.b.ult(index, &s.length);
                let unit = self.unit_at(&s, index);
                let value = self.b.zext(&unit, 32);
                self.branch_throw(path, -inside, "java/lang/StringIndexOutOfBoundsException", Val::I(value))
            }
            ("setCharAt", [Val::I(index), Val::I(ch)]) => {
                let inside = self.b.ult(index, &s.length);
                let unit = self.b.trunc(ch, 16);
                self.branch_throw_or(path, -inside, "java/lang/StringIndexOutOfBoundsException", |engine, path| {
                    let buffer = path.objects[o].array.as_mut().expect("the builder's content");
                    for (i, cell) in buffer.cells.iter_mut().enumerate() {
                        let at = engine.b.constant(i as i64, 32);
                        let selected = engine.b.eq(index, &at);
                        *cell = engine.b.ite_bits(selected, &unit, cell);
                    }
                    engine.advance(path);
                })
            }
            ("appendCodePoint", [Val::I(ch)]) => {
                let (valid, units) = self.code_point_units(ch);
                if valid != FALSE && s.cells.len() + units.cells.len() > MOST_BUILDER_CONTENT {
                    return Some(unsupported(format!("a StringBuilder of more than {MOST_BUILDER_CONTENT} code units")));
                }
                self.branch_throw_or(path, -valid, "java/lang/IllegalArgumentException", move |engine, path| {
                    path.objects[o].array = Some(engine.joined(&s, &units));
                    engine.push(path, Val::R(Some(o)));
                    engine.advance(path);
                })
            }
            ("append", [appended]) => {
                // What is appended: a String's units (`null` for null), a char, or an int's decimal digits.
                let t = match appended {
                    Val::R(None) => Array { element: Type::Char, length: self.b.constant(4, 32), cells: "null".encode_utf16().map(|u| self.b.constant(i64::from(u), 16)).collect(), refs: Vec::new() },
                    // `append(Object)` appends `String.valueOf(obj)`: a String's own units, an exception's
                    // `toString()` where the engine has it ([`super::throwables`]), and the JDK call otherwise.
                    Val::R(Some(other)) if descriptor.starts_with("(Ljava/lang/Object;)") && path.objects[*other].class != STRING => match self.throwable_text(path, *other)? {
                        Ok(super::throwables::Text::Name(units)) => Array { element: Type::Char, length: self.b.constant(units.len() as i64, 32), cells: units.iter().map(|u| self.b.constant(i64::from(*u), 16)).collect(), refs: Vec::new() },
                        Ok(super::throwables::Text::Joined(t)) => t,
                        Err(step) => return Some(step),
                    },
                    Val::R(other) => match self.string_argument(path, *other, (BUILDER, name, descriptor)) {
                        Ok(t) => t,
                        Err(step) => return Some(step),
                    },
                    Val::I(value) if descriptor.starts_with("(C)") => Array { element: Type::Char, length: self.b.constant(1, 32), cells: vec![self.b.trunc(value, 16)], refs: Vec::new() },
                    Val::I(value) | Val::J(value) => {
                        let (length, cells) = self.decimal(value);
                        Array { element: Type::Char, length, cells, refs: Vec::new() }
                    }
                    _ => return Some(unsupported(format!("StringBuilder.{name}{descriptor} with arguments {args:?}"))),
                };
                if s.cells.len() + t.cells.len() > MOST_BUILDER_CONTENT {
                    return Some(unsupported(format!("a StringBuilder of more than {MOST_BUILDER_CONTENT} code units")));
                }
                path.objects[o].array = Some(self.joined(&s, &t));
                self.push(path, Val::R(Some(o)));
                self.advance(path);
                Ok(None)
            }
            ("indexOf", [Val::R(other), rest @ ..]) => {
                let t = match self.string_argument(path, *other, (BUILDER, name, descriptor)) {
                    Ok(t) => t,
                    Err(step) => return Some(step),
                };
                let from = match rest {
                    [Val::I(from)] => from.clone(),
                    _ => self.b.constant(0, 32),
                };
                let at = self.index_of_string(&s, &t, &from);
                self.push(path, Val::I(at));
                self.advance(path);
                Ok(None)
            }
            ("substring", [Val::I(begin), Val::I(end)]) => {
                let bad = self.bad_range(begin, end, &s.length);
                let value = self.range(path, &s, begin, end, None);
                self.branch_throw(path, bad, "java/lang/StringIndexOutOfBoundsException", value)
            }
            ("delete", [Val::I(start), Val::I(end)]) => {
                // The end is held to the length; then the range is checked, and the units after it move down.
                let beyond = self.b.slt(&s.length, end);
                let end = self.b.ite_bits(beyond, &s.length, end);
                let zero = self.b.constant(0, 32);
                let below = self.b.slt(start, &zero);
                let crossed = self.b.slt(&end, start);
                let bad = self.b.or(below, crossed);
                let removed = self.b.sub(&end, start);
                let length = self.b.sub(&s.length, &removed);
                let mut cells = Vec::with_capacity(s.cells.len());
                for (i, cell) in s.cells.iter().enumerate() {
                    let here = self.b.constant(i as i64, 32);
                    let before = self.b.slt(&here, start);
                    let at = self.b.add(&here, &removed);
                    let moved = self.unit_at(&s, &at);
                    cells.push(self.b.ite_bits(before, cell, &moved));
                }
                self.branch_throw_or(path, bad, "java/lang/StringIndexOutOfBoundsException", move |engine, path| {
                    path.objects[o].array = Some(Array { element: Type::Char, length, cells, refs: Vec::new() });
                    engine.push(path, Val::R(Some(o)));
                    engine.advance(path);
                })
            }
            ("toString", []) => {
                let zero = self.b.constant(0, 32);
                let value = self.range(path, &s, &zero, &s.length.clone(), None);
                self.push(path, value);
                self.advance(path);
                Ok(None)
            }
            _ => unsupported(format!("StringBuilder.{name}{descriptor} with arguments {args:?}")),
        })
    }
}
