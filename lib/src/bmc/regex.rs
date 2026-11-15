//! `java.util.regex` as far as a claim states a glob with it, and `String.split` at one character.
//!
//! A property that says what a wildcard pattern means, independently of the code that matches it, writes the
//! pattern as a regular expression: each part between two `*` quoted, the parts joined by `.*`, the whole compiled
//! and matched against the field (`Pattern.compile(String.join(".*", Arrays.stream(p.split("\\*", -1))
//! .map(Pattern::quote).toArray(String[]::new)), CASE_INSENSITIVE | DOTALL).matcher(field).matches()`). The engine
//! follows that by what each call means, not by the text it builds: a String that is a regular expression is held
//! as its pieces ([`Regex::Source`]), not as characters, a Pattern as its pieces and flags, a Matcher as those and
//! its input, and `matches()` is a formula that says whether the whole input is in the language of the pieces.
//!
//! - `String.split(String, int)` on a String whose content the engine holds, with a regex that is a constant of
//!   one character that stands for itself (any but `.$|()[{^?*+\`), or of `\` and one character that is no ASCII
//!   letter or digit (the JDK's own fast path, by its source), and a limit that is a negative constant: the units
//!   between the occurrences, every one kept, the String itself where there is none. Each part is the JDK's
//!   `substring` ([`Engine::range`]): the literal `""` where it is empty. `NullPointerException` for a null regex.
//!   Any other regex or limit is refused, as the call was (its result is an array).
//! - `Pattern.quote(String)`: a String that, as a regular expression, matches the argument's units and nothing
//!   else (its Javadoc). `NullPointerException` for null.
//! - `String.join(CharSequence, CharSequence...)` where the delimiter is a constant in the syntax below and an
//!   element is such a quoted String: the regular expression that is the elements in sequence, the delimiter
//!   between each two; a null element is the four characters `null`. Any other join is the JDK call it was.
//! - `Pattern.compile(String, int)`, and `Pattern.compile(String)`, of such a String, or (the first) of a constant
//!   in the syntax below, with no flag but `CASE_INSENSITIVE` and `DOTALL`: a Pattern of those pieces.
//! - `Pattern.matcher(CharSequence)` of such a Pattern and a String whose content the engine holds: a Matcher.
//!   `NullPointerException` for null.
//! - `Matcher.matches()` of such a Matcher: whether the pieces match the whole input.
//!
//! The syntax of a constant: a character that stands for itself (an ASCII letter or digit, the space and
//! `! " # % & ' , - / : ; < = > @ _ ` ~`), `\` before an ASCII punctuation character, and `.`, each followed by at
//! most one `*`. Nothing else: no class, group, alternative, anchor or other quantifier.
//!
//! What `matches()` says is membership in a regular language, so the order in which the JDK's matcher tries the
//! alternatives does not matter. A literal unit matches itself; under `CASE_INSENSITIVE` (without
//! `UNICODE_CASE`, which is refused) two units also match when both are ASCII letters that differ in case, as the
//! JDK's `ASCII.toLower` comparison does; `.` matches any unit under `DOTALL`, and any but the line terminators
//! `\n`, `\r`, `\u0085`, ` ` and ` ` without it. The JDK matches by code point, which differs from
//! matching by unit only where a surrogate is: an input or a quoted part with a surrogate unit is the JDK call it
//! was (a gap). Any other method of such a Matcher makes it an object the engine knows nothing of again.

use super::*;

const PATTERN: &str = "java/util/regex/Pattern";
const MATCHER: &str = "java/util/regex/Matcher";
const CASE_INSENSITIVE: i64 = 2;
const DOTALL: i64 = 32;

/// A sequence of units: a String's content when the tag was made (a String never changes).
#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct Text {
    length: Bits,
    cells: Vec<Bits>,
}

impl Text {
    fn of(s: &Array) -> Text {
        Text { length: s.length.clone(), cells: s.cells.clone() }
    }
}

/// How `String.split` cut a String at a character: the String's units, where the character is (`is[i]`: at the
/// index `i`, inside the length), and how many parts that makes (the length of the array it returned).
#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct Split {
    text: Text,
    is: Vec<Lit>,
    parts: Bits,
}

/// What matches one unit: any, or one constant.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Atom {
    Any,
    Unit(u16),
}

/// A piece of a regular expression: an atom once, an atom any number of times, a quoted text (and the part of a
/// split it is, where it is one), or every part of a split quoted, in order, with atoms between each two (each
/// once, or any number of times where its flag says so).
#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) enum Kind {
    One(Atom),
    Star(Atom),
    Text(Text, Option<(Rc<Split>, usize)>),
    Parts(Rc<Split>, Vec<(Atom, bool)>),
}

/// A piece that is there when `when` holds, and matches the empty sequence otherwise (an element of a joined
/// array at an index its length may or may not reach).
#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct Piece {
    when: Lit,
    kind: Kind,
}

/// What the engine knows of an object beyond its content: what it means as a regular expression (a String with no
/// content it holds, a Pattern, a Matcher), or, of a String whose content it holds, how it was made: the part of
/// a split it is, or the units it is the lower case of. See the module's notes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) enum Regex {
    Source(Vec<Piece>),
    Pattern(Vec<Piece>, i64),
    Matcher(Vec<Piece>, i64, Text),
    Part(Rc<Split>, usize),
    Lowered(Text),
}

impl Regex {
    /// The tag of a String that is `original`'s units, each ASCII upper-case letter lowered.
    pub(super) fn lowered(original: &Array) -> Regex {
        Regex::Lowered(Text::of(original))
    }
}

/// Whether the engine models `String.name(descriptor)` here.
pub fn models_string(name: &str, descriptor: &str) -> bool {
    (name, descriptor) == ("split", "(Ljava/lang/String;I)[Ljava/lang/String;")
}

/// Whether the engine models the static call here, where its arguments let it.
pub fn models_static(owner: &str, name: &str, descriptor: &str) -> bool {
    matches!(
        (owner, name, descriptor),
        (PATTERN, "quote", "(Ljava/lang/String;)Ljava/lang/String;") | (PATTERN, "compile", "(Ljava/lang/String;I)Ljava/util/regex/Pattern;") | (STRING, "join", "(Ljava/lang/CharSequence;[Ljava/lang/CharSequence;)Ljava/lang/String;")
    )
}

/// The pieces of a constant regular expression in the module's syntax, each an atom with or without a star as
/// `(atom, starred)`; `None` for any other.
pub fn parse(units: &[u16]) -> Option<Vec<(Atom, bool)>> {
    let ascii = |u: u16| char::from_u32(u32::from(u)).filter(char::is_ascii);
    let mut pieces = Vec::new();
    let mut i = 0;
    while i < units.len() {
        let atom = match ascii(units[i])? {
            '.' => Atom::Any,
            '\\' => {
                i += 1;
                Atom::Unit(ascii(*units.get(i)?).filter(char::is_ascii_punctuation)? as u16)
            }
            c if c.is_ascii_alphanumeric() || " !\"#%&',-/:;<=>@_`~".contains(c) => Atom::Unit(c as u16),
            _ => return None,
        };
        i += 1;
        let starred = units.get(i) == Some(&u16::from(b'*'));
        i += usize::from(starred);
        pieces.push((atom, starred));
    }
    Some(pieces)
}

/// The character `String.split` splits at without a Pattern, for a regex of these units: the JDK's fast path.
pub fn split_character(units: &[u16]) -> Option<u16> {
    let surrogate = |u: u16| (0xD800..=0xDFFF).contains(&u);
    let alphanumeric = |u: u16| char::from_u32(u32::from(u)).is_some_and(|c| c.is_ascii_alphanumeric());
    match units {
        [c] if !".$|()[{^?*+\\".encode_utf16().any(|m| m == *c) && !surrogate(*c) => Some(*c),
        [b, c] if *b == u16::from(b'\\') && !alphanumeric(*c) && !surrogate(*c) => Some(*c),
        _ => None,
    }
}

impl Engine<'_> {
    /// A new object of `class` that is the regular expression `regex`. A String among them has no characters the
    /// engine holds, and reading it as text ends the run with no verdict.
    fn regex_object(&mut self, path: &mut Path, class: &str, regex: Regex) -> usize {
        let limit = (class == STRING).then(|| "a String the engine holds as the regular expression it is and not as its characters (the result of Pattern.quote, or of a String.join of such), read as text".to_string());
        path.objects.push(Obj { regex: Some(Rc::new(regex)), limit, ..Obj::new(class) });
        path.objects.len() - 1
    }

    /// The pieces the String `o` is as a regular expression: its tag, or a constant's in the module's syntax.
    fn regex_source(&self, path: &Path, o: usize) -> Option<Vec<Piece>> {
        if let Some(Regex::Source(pieces)) = path.objects[o].regex.as_deref() {
            return Some(pieces.clone());
        }
        let units = self.constant_units(path, o)?;
        Some(parse(&units)?.into_iter().map(|(atom, starred)| Piece { when: TRUE, kind: if starred { Kind::Star(atom) } else { Kind::One(atom) } }).collect())
    }

    /// `String.split(regex, limit)` on the String `o` of content `s`: see the module's notes.
    pub(super) fn string_split(&mut self, path: &mut Path, o: usize, s: &Array, args: &[Val]) -> Step {
        let [Val::R(regex), Val::I(limit)] = args else { return unsupported(format!("String.split with arguments {args:?}")) };
        let Some(regex) = *regex else { return self.raise(path, "java/lang/NullPointerException") };
        let delimiter = self.constant_units(path, regex).and_then(|units| split_character(&units));
        let every_part = self.b.constant_value(limit).is_some_and(|l| l < 0);
        let (Some(delimiter), true) = (delimiter, every_part) else {
            return unsupported("String.split with a regex that is not a constant of one character that stands for itself, or a limit that is not a negative constant");
        };
        let n = s.cells.len();
        let unit = self.b.constant(i64::from(delimiter), 16);
        // A String that is another's units lowered has the delimiter where the other has it, when the delimiter
        // is no ASCII letter: the test reads the other's units, so that a split of each is one formula.
        let letter = char::from_u32(u32::from(delimiter)).is_some_and(|c| c.is_ascii_alphabetic());
        let tested: Vec<Bits> = match path.objects[o].regex.as_deref() {
            Some(Regex::Lowered(original)) if !letter && original.cells.len() == n => original.cells.clone(),
            _ => s.cells.clone(),
        };
        // `before[i]`: exactly `i` delimiters are before the index reached; `ends[i]`: the index of the `i`th.
        let mut before = vec![TRUE];
        let mut ends = vec![s.length.clone(); n + 1];
        let mut found = vec![FALSE; n + 1];
        let mut delimiters = Vec::with_capacity(n);
        for (j, cell) in tested.iter().enumerate() {
            let here = self.b.constant(j as i64, 32);
            let inside = self.b.slt(&here, &s.length);
            let equal = self.b.eq(cell, &unit);
            let is = self.b.and(inside, equal);
            delimiters.push(is);
            let mut next = vec![FALSE; before.len() + 1];
            for (i, &so_far) in before.iter().enumerate() {
                let hit = self.b.and(so_far, is);
                if hit != FALSE {
                    ends[i] = self.b.ite_bits(hit, &here, &ends[i]);
                    found[i] = self.b.or(found[i], hit);
                }
                let stays = self.b.and(so_far, -is);
                next[i] = self.b.or(next[i], stays);
                next[i + 1] = hit;
            }
            before = next;
        }
        let mut count = self.b.constant(0, 32);
        for (i, &exactly) in before.iter().enumerate().skip(1) {
            let this = self.b.constant(i as i64, 32);
            count = self.b.ite_bits(exactly, &this, &count);
        }
        let one = self.b.constant(1, 32);
        let length = self.b.add(&count, &one);
        let zero = self.b.constant(0, 32);
        let split = Rc::new(Split { text: Text::of(s), is: delimiters, parts: length.clone() });
        let mut refs = Vec::with_capacity(n + 1);
        for i in 0..=n {
            // A part the array's length does not reach is empty, and never read.
            let begin = match i {
                0 => zero.clone(),
                _ => {
                    let after = self.b.add(&ends[i - 1], &one);
                    self.b.ite_bits(found[i - 1], &after, &s.length)
                }
            };
            let part = self.range(path, s, &begin, &ends[i], (i == 0).then_some(o));
            // A part that is a String of its own remembers which part it is.
            if let Val::R(Some(p)) = part {
                if p != o && path.objects[p].regex.is_none() && !path.literals.values().any(|&l| l == p) {
                    path.objects[p].regex = Some(Rc::new(Regex::Part(split.clone(), i)));
                }
            }
            refs.push(part);
        }
        let element = Type::Object(STRING.to_string());
        path.objects.push(Obj { array: Some(Array { element, length, cells: Vec::new(), refs }), ..Obj::new("[Ljava/lang/String;") });
        let array = path.objects.len() - 1;
        self.push(path, Val::R(Some(array)));
        self.advance(path);
        Ok(None)
    }

    /// `Pattern.quote`, `String.join` and `Pattern.compile(String, int)`: see the module's notes. `None` where the
    /// call stays the JDK's.
    pub(super) fn regex_static(&mut self, path: &mut Path, owner: &str, name: &str, args: &[Val]) -> Option<Step> {
        let null = |engine: &mut Self, path: &mut Path| Some(engine.raise(path, "java/lang/NullPointerException"));
        let value = match (owner, name, args) {
            (PATTERN, "quote", [Val::R(quoted)]) => {
                let Some(quoted) = *quoted else { return null(self, path) };
                let text = Text::of(path.objects[quoted].content()?);
                let part = match path.objects[quoted].regex.as_deref() {
                    Some(Regex::Part(split, k)) => Some((split.clone(), *k)),
                    _ => None,
                };
                self.regex_object(path, STRING, Regex::Source(vec![Piece { when: TRUE, kind: Kind::Text(text, part) }]))
            }
            (STRING, "join", [Val::R(delimiter), Val::R(elements)]) => {
                let Some(delimiter) = *delimiter else { return null(self, path) };
                let Some(elements) = *elements else { return null(self, path) };
                if path.objects[delimiter].class != STRING || path.objects[delimiter].regex.is_some() {
                    return None;
                }
                let between = self.regex_source(path, delimiter)?;
                let array = path.objects[elements].as_array()?.clone();
                // A join with no quoted element is text, which this is no model of.
                let quoted = |r: &Val| r.options().is_some_and(|options| options.iter().any(|(_, e)| e.is_some_and(|e| matches!(path.objects[e].regex.as_deref(), Some(Regex::Source(_))))));
                if !array.refs.iter().any(quoted) {
                    return None;
                }
                let mut pieces = Vec::new();
                for (i, element) in array.refs.iter().enumerate() {
                    let here = self.b.constant(i as i64, 32);
                    let inside = self.b.slt(&here, &array.length);
                    if inside == FALSE {
                        continue;
                    }
                    if i > 0 {
                        pieces.extend(between.iter().map(|piece| Piece { when: inside, kind: piece.kind.clone() }));
                    }
                    // The element is one of its options: the pieces of each, there where it is that one.
                    for (is, option) in element.options()? {
                        let of_option = match option {
                            Some(e) if path.objects[e].class == STRING => self.regex_source(path, e)?,
                            Some(_) => return None,
                            None => "null".encode_utf16().map(|u| Piece { when: TRUE, kind: Kind::One(Atom::Unit(u)) }).collect(),
                        };
                        let there = self.b.and(inside, is);
                        for piece in of_option {
                            let when = self.b.and(there, piece.when);
                            pieces.push(Piece { when, kind: piece.kind });
                        }
                    }
                }
                let pieces = match self.all_parts(path, &between, &array) {
                    Ok(Some(parts)) => vec![parts],
                    Ok(None) => pieces,
                    Err(stop) => return Some(Err(stop)),
                };
                self.regex_object(path, STRING, Regex::Source(pieces))
            }
            (PATTERN, "compile", [Val::R(regex), Val::I(flags)]) => {
                let Some(regex) = *regex else { return null(self, path) };
                let flags = self.b.constant_value(flags).filter(|f| f & !(CASE_INSENSITIVE | DOTALL) == 0)?;
                let pieces = self.regex_source(path, regex)?;
                self.regex_object(path, PATTERN, Regex::Pattern(pieces, flags))
            }
            _ => return None,
        };
        self.push(path, Val::R(Some(value)));
        self.advance(path);
        Some(Ok(None))
    }

    /// The one piece a join is when its elements are the parts of one split, each quoted, all of them and in
    /// order: the split's String with `between` at each delimiter ([`Kind::Parts`]), which is one formula however
    /// the parts were cut and the array filled. `None` for any other join. That the array holds every part, and
    /// nothing else within its length, is the solver's to show on the path where it is not plain.
    fn all_parts(&mut self, path: &Path, between: &[Piece], array: &Array) -> Result<Option<Piece>, Stop> {
        let mut atoms = Vec::with_capacity(between.len());
        for piece in between {
            match (&piece.kind, piece.when) {
                (Kind::One(atom), TRUE) => atoms.push((atom.clone(), false)),
                (Kind::Star(atom), TRUE) => atoms.push((atom.clone(), true)),
                _ => return Ok(None),
            }
        }
        let part_of = |e: usize| match path.objects[e].regex.as_deref() {
            Some(Regex::Source(pieces)) => match pieces.as_slice() {
                [Piece { when: TRUE, kind: Kind::Text(_, Some((split, k))) }] => Some((split.clone(), *k)),
                _ => None,
            },
            _ => None,
        };
        let mut split: Option<Rc<Split>> = None;
        // Where the array is not the parts: an element within its length that is null, or a length that is not
        // the number of parts.
        let mut other = Vec::new();
        for (i, element) in array.refs.iter().enumerate() {
            let here = self.b.constant(i as i64, 32);
            let inside = self.b.slt(&here, &array.length);
            let Some(options) = element.options() else { return Ok(None) };
            for (is, option) in options {
                // A cell past the split's last possible part is past the array's length, or the array is not the
                // parts.
                if split.as_ref().is_some_and(|s| i > s.is.len()) {
                    other.push(inside);
                    continue;
                }
                match option {
                    None => other.push(self.b.and(inside, is)),
                    Some(e) => match (part_of(e), &split) {
                        (Some((s, k)), None) if k == i => split = Some(s),
                        (Some((s, k)), Some(first)) if k == i && (Rc::ptr_eq(&s, first) || s == *first) => {}
                        _ => return Ok(None),
                    },
                }
            }
        }
        let Some(split) = split else { return Ok(None) };
        other.push(-self.b.eq(&array.length, &split.parts));
        let other = self.any(&other);
        if other != FALSE {
            let mut assumptions = path.cond.clone();
            assumptions.push(other);
            if self.solve(&assumptions)? {
                return Ok(None);
            }
        }
        Ok(Some(Piece { when: TRUE, kind: Kind::Parts(split, atoms) }))
    }

    /// `Pattern.compile(String)` of the String `o` that is a regular expression by its tag: a Pattern of its
    /// pieces. `None` for any other String.
    pub(super) fn compile_source(&mut self, path: &mut Path, o: usize) -> Option<Step> {
        let Some(Regex::Source(pieces)) = path.objects[o].regex.as_deref() else { return None };
        let pieces = pieces.clone();
        let pattern = self.regex_object(path, PATTERN, Regex::Pattern(pieces, 0));
        self.push(path, Val::R(Some(pattern)));
        self.advance(path);
        Some(Ok(None))
    }

    /// `Pattern.matcher` and `Matcher.matches` on the object `o`, where it is a Pattern or a Matcher of pieces: see
    /// the module's notes. `None` where the call stays the JDK's.
    pub(super) fn regex_method(&mut self, path: &mut Path, o: usize, name: &str, descriptor: &str, args: &[Val]) -> Option<Step> {
        match (path.objects[o].regex.as_deref()?.clone(), name, descriptor, args) {
            (Regex::Pattern(pieces, flags), "matcher", "(Ljava/lang/CharSequence;)Ljava/util/regex/Matcher;", [Val::R(input)]) => {
                let Some(input) = *input else { return Some(self.raise(path, "java/lang/NullPointerException")) };
                let text = Text::of(path.objects[input].content()?);
                let matcher = self.regex_object(path, MATCHER, Regex::Matcher(pieces, flags, text));
                self.push(path, Val::R(Some(matcher)));
                self.advance(path);
                Some(Ok(None))
            }
            (Regex::Matcher(pieces, flags, input), "matches", "()Z", []) => {
                let (truth, surrogate) = self.matches(&pieces, flags, &input);
                Some(self.branch_gap_or(path, surrogate, (GapKind::JdkReferenceMethod, MATCHER, name, descriptor), move |engine, path| engine.push_truth(path, truth)))
            }
            (Regex::Matcher(..), _, _, _) => {
                // Any other method may change what the Matcher matches (its region, its input, its pattern).
                path.objects[o].regex = None;
                None
            }
            _ => None,
        }
    }

    /// Whether `pieces`, under `flags`, match the whole of `input`, and whether a surrogate is among the units
    /// compared (where matching by unit is not the JDK's matching by code point).
    fn matches(&mut self, pieces: &[Piece], flags: i64, input: &Text) -> (Lit, Lit) {
        let insensitive = flags & CASE_INSENSITIVE != 0;
        let n = input.cells.len();
        let mut surrogates = Vec::new();
        let inside_surrogates = |engine: &mut Self, text: &Text, when: Lit, surrogates: &mut Vec<Lit>| {
            let (mask, high) = (engine.b.constant(0xF800, 16), engine.b.constant(0xD800, 16));
            for (i, cell) in text.cells.iter().enumerate() {
                let here = engine.b.constant(i as i64, 32);
                let inside = engine.b.slt(&here, &text.length);
                let top = engine.b.and_bits(cell, &mask);
                let is = engine.b.eq(&top, &high);
                surrogates.push(engine.b.all(&[when, inside, is]));
            }
        };
        inside_surrogates(self, input, TRUE, &mut surrogates);
        let units: Vec<Bits> = input.cells.iter().map(|c| self.folded(c, insensitive)).collect();
        // `reach[j]`: the pieces so far match the first `j` units of the input. A unit at or past the input's
        // length may be reached too, and never counts: positions only grow, and the end asks for the length.
        let mut reach = vec![FALSE; n + 1];
        reach[0] = TRUE;
        for piece in pieces {
            if piece.when == FALSE {
                continue;
            }
            let next = match &piece.kind {
                Kind::One(atom) => self.atom_step(&reach, atom, false, flags, input, &units),
                Kind::Star(atom) => self.atom_step(&reach, atom, true, flags, input, &units),
                Kind::Text(text, _) => {
                    inside_surrogates(self, text, piece.when, &mut surrogates);
                    let quoted: Vec<Bits> = text.cells.iter().map(|c| self.folded(c, insensitive)).collect();
                    let lengths: Vec<Lit> = (0..=quoted.len())
                        .map(|a| {
                            let this = self.b.constant(a as i64, 32);
                            self.b.eq(&text.length, &this)
                        })
                        .collect();
                    let mut ending: Vec<Vec<Lit>> = vec![Vec::new(); n + 1];
                    for start in 0..=n {
                        // `so_far`: reached `start`, and the first `a` units of the text are the input's from there.
                        let mut so_far = reach[start];
                        for a in 0..=quoted.len().min(n - start) {
                            if so_far == FALSE {
                                break;
                            }
                            let whole = self.b.and(so_far, lengths[a]);
                            ending[start + a].push(whole);
                            if a < quoted.len() && start + a < n {
                                let same = self.b.eq(&quoted[a], &units[start + a]);
                                so_far = self.b.and(so_far, same);
                            }
                        }
                    }
                    ending.iter().map(|ways| self.any(ways)).collect()
                }
                // The split's String unit by unit: at a delimiter the atoms between two parts, at any other unit
                // that unit itself.
                Kind::Parts(split, between) => {
                    inside_surrogates(self, &split.text, piece.when, &mut surrogates);
                    let mut reached = reach.clone();
                    for (i, cell) in split.text.cells.iter().enumerate() {
                        let quoted = self.folded(cell, insensitive);
                        let mut unit = vec![FALSE; n + 1];
                        for j in 0..n {
                            let same = self.b.eq(&quoted, &units[j]);
                            unit[j + 1] = self.b.and(reached[j], same);
                        }
                        let mut delimiter = reached.clone();
                        for (atom, starred) in between {
                            delimiter = self.atom_step(&delimiter, atom, *starred, flags, input, &units);
                        }
                        let here = self.b.constant(i as i64, 32);
                        let inside = self.b.slt(&here, &split.text.length);
                        for j in 0..=n {
                            let stepped = self.b.ite(split.is[i], delimiter[j], unit[j]);
                            reached[j] = self.b.ite(inside, stepped, reached[j]);
                        }
                    }
                    reached
                }
            };
            reach = match piece.when {
                TRUE => next,
                when => next.iter().zip(&reach).map(|(after, before)| self.b.ite(when, *after, *before)).collect(),
            };
        }
        let ends: Vec<Lit> = reach
            .iter()
            .enumerate()
            .map(|(j, &reached)| {
                let here = self.b.constant(j as i64, 32);
                let is_end = self.b.eq(&input.length, &here);
                self.b.and(reached, is_end)
            })
            .collect();
        let truth = self.any(&ends);
        (truth, self.any(&surrogates))
    }

    /// The unit as two units are compared: itself, or, ignoring ASCII case, an ASCII upper-case letter lowered
    /// (the formula `String.toLowerCase()`'s model makes of the unit, [`Engine::lowered_ascii`]).
    fn folded(&mut self, unit: &Bits, insensitive: bool) -> Bits {
        if insensitive {
            self.lowered_ascii(unit).1
        } else {
            unit.clone()
        }
    }

    /// The positions the pieces so far and then `atom` reach, from those `reach`ed: once, or any number of times.
    fn atom_step(&mut self, reach: &[Lit], atom: &Atom, starred: bool, flags: i64, input: &Text, units: &[Bits]) -> Vec<Lit> {
        let n = units.len();
        let mut next = vec![FALSE; n + 1];
        if starred {
            next[0] = reach[0];
        }
        for j in 0..n {
            let fits = self.atom_matches(atom, flags, &input.cells[j], &units[j]);
            next[j + 1] = if starred {
                let longer = self.b.and(next[j], fits);
                self.b.or(reach[j + 1], longer)
            } else {
                self.b.and(reach[j], fits)
            };
        }
        next
    }

    /// Whether `atom` matches the input unit `raw`, which is `unit` as units are compared.
    fn atom_matches(&mut self, atom: &Atom, flags: i64, raw: &Bits, unit: &Bits) -> Lit {
        match atom {
            Atom::Unit(u) => {
                let lowered = if flags & CASE_INSENSITIVE != 0 && (u16::from(b'A')..=u16::from(b'Z')).contains(u) { u | 0x20 } else { *u };
                let constant = self.b.constant(i64::from(lowered), 16);
                self.b.eq(unit, &constant)
            }
            Atom::Any if flags & DOTALL != 0 => TRUE,
            Atom::Any => {
                let terminators: Vec<Lit> = [0x0A, 0x0D, 0x85, 0x2028, 0x2029]
                    .into_iter()
                    .map(|t| {
                        let constant = self.b.constant(t, 16);
                        self.b.eq(raw, &constant)
                    })
                    .collect();
                -self.any(&terminators)
            }
        }
    }
}
