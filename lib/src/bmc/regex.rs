//! `java.util.regex` as far as a claim states a glob or a text's shape with it, and `String.split` at one character.
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
//!   in the syntax below, with no flag but `CASE_INSENSITIVE` and `DOTALL`: a Pattern of those pieces. Either
//!   flag may be chosen by an input ([`Flags`]); that no other is set is the solver's to show on the path.
//! - `Pattern.compile(String, int)` of a String that is an input, where the solver shows that on the path it can
//!   only be characters that stand for themselves (the syntax below) followed by `.*`, as a protective rule
//!   `/admin/.*` is, with the same flags: a Pattern of the characters as a quoted text, then `.` any number of
//!   times ([`Engine::literal_then_any`]). Nothing is assumed of the String: where it may be anything else, the
//!   call is the JDK's, a gap.
//! - `Pattern.matcher(CharSequence)` of such a Pattern and a String whose content the engine holds: a Matcher.
//!   `NullPointerException` for null.
//! - `Matcher.matches()` of such a Matcher: whether the pieces match the whole input.
//!
//! The syntax of a constant, in ASCII: a character that stands for itself (a letter or digit, the space and
//! `! " # % & ' , - / : ; < = > @ _ ` ~`), `\` before a punctuation character, `\t \n \r \f \e \a`, `.`, the
//! classes `\d \w \s` and their complements `\D \W \S` (ASCII's, as without `UNICODE_CHARACTER_CLASS`), a class in
//! brackets (characters, ranges, `\d \w \s` and escaped punctuation, negated by a leading `^`; no nested class and
//! no intersection), a group (`(` or `(?:`, which differ only in what a match records, not in what matches),
//! alternatives (`|`), the quantifiers `*`, `+`, `?`, `{n}`, `{n,}` and `{n,m}` (greedy: a reluctant one is the same
//! language and is refused all the same, a possessive one is not), and the anchors `\A`, `^` (the input's
//! beginning, without `MULTILINE`) and `\z`. Nothing else: no `$` (which also matches before a last line
//! terminator), back reference, look-around or inline flag. Standalone Unicode block atoms support Basic Latin
//! and Combining Diacritical Marks, with their complements. With `CASE_INSENSITIVE`, literals and
//! bracket ranges match both ASCII cases. Negation applies to the resulting character set.
//!
//! - `String.matches(String)` of a String whose content the engine holds and a regex that is such a constant:
//!   whether the regex matches the whole String. `NullPointerException` for a null regex.
//!
//! What `matches()` says is membership in a regular language, so the order in which the JDK's matcher tries the
//! alternatives does not matter. A literal unit matches itself; under `CASE_INSENSITIVE` (without
//! `UNICODE_CASE`, which is refused) two units also match when both are ASCII letters that differ in case, as the
//! JDK's `ASCII.toLower` comparison does; `.` matches any unit under `DOTALL`, and any but the line terminators
//! `\n`, `\r`, `\u0085`, ` ` and ` ` without it. The JDK matches by code point, which differs from
//! matching by unit only where a surrogate is matched: a quoted part with a surrogate unit is the JDK call it was
//! (a gap), and so is an input with one where the regular expression has something a surrogate could match (`.`, a
//! negated class, a class with one in a range). Where every atom is a set of units that has no surrogate, a
//! surrogate in the input matches nothing by unit and nothing by code point (alone it is its own code point, in a
//! pair it is part of a supplementary one, and neither is in the set), so matching by unit is the JDK's matching.
//! One `.*` that ends such an expression takes surrogates too: what comes before it matched no surrogate, so it
//! begins at the input's beginning or after a unit that is none, which is never inside a pair; from there the rest
//! of the input is whole code points, a pair is no line terminator, and a surrogate alone is its own code point and
//! none either, so the rest is `.*` by code point exactly when each of its units is `.` by unit.
//! `group(int)` after a full match returns the whole input or a mandatory capture with provable UTF-16
//! boundaries. Reading an optional or ambiguous capture refuses the observation. Other Matcher methods invalidate its state.

use super::*;

const PATTERN: &str = "java/util/regex/Pattern";
const MATCHER: &str = "java/util/regex/Matcher";
const MATCH_INPUT: &str = "java/util/regex/Matcher#input";
const MATCH_SUCCESS: &str = "java/util/regex/Matcher#matched";
/// The bits of `Pattern.CASE_INSENSITIVE` (2) and `Pattern.DOTALL` (32) in a flags argument.
const CASE_INSENSITIVE: usize = 1;
const DOTALL: usize = 5;

/// The two flags the module reads, each a formula: a constructor may choose them by an input, and paths that chose
/// differently may have met again before the Pattern is compiled.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(super) struct Flags {
    insensitive: Lit,
    dotall: Lit,
}

const NO_FLAGS: Flags = Flags { insensitive: FALSE, dotall: FALSE };

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

/// What matches one unit: any, one constant, or a class (the units of its ranges, or every other unit when it
/// is negated).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Atom {
    Any,
    Unit(u16),
    Class(Vec<(u16, u16)>, bool),
}

impl Atom {
    /// Whether the atom may match a surrogate unit, where matching by unit is not the JDK's matching.
    fn wide(&self) -> bool {
        let surrogates = (0xD800u16, 0xDFFFu16);
        match self {
            Atom::Any => true,
            Atom::Unit(u) => (surrogates.0..=surrogates.1).contains(u),
            Atom::Class(_, true) => true,
            Atom::Class(ranges, false) => ranges.iter().any(|(lo, hi)| *lo <= surrogates.1 && *hi >= surrogates.0),
        }
    }
}

/// A constant regular expression in the module's syntax.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Node {
    One(Atom),
    Seq(Vec<Node>),
    Alt(Vec<Node>),
    Capture(usize, Box<Node>),
    /// At least the first number of times, and at most the second, or any number where there is none.
    Repeat(Box<Node>, u32, Option<u32>),
    /// The input's beginning (`\A`, `^`) and its end (`\z`).
    Begin,
    End,
}

impl Node {
    fn wide(&self) -> bool {
        match self {
            Node::One(atom) => atom.wide(),
            Node::Seq(nodes) | Node::Alt(nodes) => nodes.iter().any(Node::wide),
            Node::Repeat(node, _, _) | Node::Capture(_, node) => node.wide(),
            Node::Begin | Node::End => false,
        }
    }

    /// A fixed UTF-16 width on successful matches in the supported code-unit fragment.
    fn width(&self) -> Option<i32> {
        match self {
            Node::One(_) => Some(1),
            Node::Begin | Node::End => Some(0),
            Node::Capture(_, body) => body.width(),
            Node::Seq(nodes) => widths(nodes, Some(0)),
            Node::Alt(nodes) => {
                let first = nodes.first()?.width()?;
                nodes.iter().all(|n| n.width() == Some(first)).then_some(first)
            }
            Node::Repeat(body, min, max) => {
                let width = body.width()?;
                if width == 0 { Some(0) } else if *max == Some(*min) { width.checked_mul(*min as i32) } else { None }
            }
        }
    }

    fn last_group(&self) -> usize {
        match self {
            Node::Capture(id, body) => (*id).max(body.last_group()),
            Node::Seq(nodes) | Node::Alt(nodes) => nodes.iter().map(Node::last_group).max().unwrap_or(0),
            Node::Repeat(body, _, _) => body.last_group(),
            _ => 0,
        }
    }

    /// Absolute offsets are known from the beginning, from the end, or from a fixed
    /// group width and one of those boundaries. We require one mandatory occurrence:
    /// optional, repeated and alternative captures can depend on backtracking history.
    fn capture(&self, group: usize, prefix: Option<i32>, suffix: Option<i32>) -> Option<(Offset, Offset)> {
        match self {
            Node::Capture(id, body) if *id == group => {
                match (prefix, suffix) {
                    (Some(a), Some(b)) => Some((Offset::Start(a), Offset::End(b))),
                    (Some(a), None) => Some((Offset::Start(a), Offset::Start(a.checked_add(body.width()?)?))),
                    (None, Some(b)) => Some((Offset::End(b.checked_add(body.width()?)?), Offset::End(b))),
                    _ => None,
                }
            }
            Node::Capture(_, body) => body.capture(group, prefix, suffix),
            Node::Seq(nodes) => {
                // Groups are numbered at their opening parenthesis, from left to right.
                let i = nodes.iter().position(|n| n.last_group() >= group)?;
                nodes[i].capture(group, widths(&nodes[..i], prefix), widths(&nodes[i + 1..], suffix))
            }
            _ => None,
        }
    }

    /// The expression as atoms in sequence, each once or any number of times, where it is that.
    fn flat(&self) -> Option<Vec<(Atom, bool)>> {
        let Node::Seq(nodes) = self else { return None };
        nodes
            .iter()
            .map(|node| match node {
                Node::One(atom @ (Atom::Any | Atom::Unit(_))) => Some((atom.clone(), false)),
                Node::Repeat(inner, 0, None) => match &**inner {
                    Node::One(atom @ (Atom::Any | Atom::Unit(_))) => Some((atom.clone(), true)),
                    _ => None,
                },
                _ => None,
            })
            .collect()
    }
}

fn widths(nodes: &[Node], offset: Option<i32>) -> Option<i32> {
    nodes.iter().try_fold(offset?, |sum, n| sum.checked_add(n.width()?))
}

enum Offset {
    Start(i32),
    End(i32),
}

impl Offset {
    fn resolve(&self, bits: &mut Blaster, length: &Bits) -> Bits {
        match *self {
            Offset::Start(i) => bits.constant(i64::from(i), 32),
            Offset::End(i) => {
                let tail = bits.constant(i64::from(i), 32);
                bits.sub(length, &tail)
            }
        }
    }
}

/// The most a counted quantifier may count to here.
const MOST_REPEATS: u32 = 1024;

/// A reader of a constant regular expression's units.
struct Reader<'a> {
    units: &'a [u16],
    at: usize,
    groups: usize,
}

impl Reader<'_> {
    /// The next unit as an ASCII character, if there is one and it is one.
    fn peek(&self) -> Option<char> {
        self.units.get(self.at).and_then(|u| char::from_u32(u32::from(*u))).filter(char::is_ascii)
    }

    fn done(&self) -> bool {
        self.at >= self.units.len()
    }

    fn eat(&mut self, c: char) -> bool {
        let is = self.peek() == Some(c);
        self.at += usize::from(is);
        is
    }

    fn alternatives(&mut self) -> Option<Node> {
        let mut branches = vec![self.sequence()?];
        while self.eat('|') {
            branches.push(self.sequence()?);
        }
        Some(if branches.len() == 1 { branches.pop().expect("a branch") } else { Node::Alt(branches) })
    }

    fn sequence(&mut self) -> Option<Node> {
        let mut nodes = Vec::new();
        while !self.done() && !matches!(self.peek()?, '|' | ')') {
            let atom = self.atom()?;
            nodes.push(self.quantified(atom)?);
        }
        Some(Node::Seq(nodes))
    }

    fn atom(&mut self) -> Option<Node> {
        let c = self.peek()?;
        self.at += 1;
        Some(match c {
            '.' => Node::One(Atom::Any),
            '^' => Node::Begin,
            '\\' => {
                let e = self.peek()?;
                self.at += 1;
                match e {
                    'A' => Node::Begin,
                    'z' => Node::End,
                    'D' | 'W' | 'S' => Node::One(Atom::Class(shorthand(e.to_ascii_lowercase())?, true)),
                    'd' | 'w' | 's' => Node::One(Atom::Class(shorthand(e)?, false)),
                    'p' | 'P' => Node::One(Atom::Class(vec![self.unicode_block()?], e == 'P')),
                    _ => Node::One(Atom::Unit(escaped(e)?)),
                }
            }
            '[' => {
                let negated = self.eat('^');
                let mut ranges = Vec::new();
                loop {
                    let c = self.peek()?;
                    self.at += 1;
                    let low = match c {
                        ']' if !ranges.is_empty() => break,
                        ']' | '[' => return None,
                        '&' if self.peek() == Some('&') => return None,
                        '\\' => {
                            let e = self.peek()?;
                            self.at += 1;
                            if let Some(class) = shorthand(e) {
                                ranges.extend(class);
                                continue;
                            }
                            escaped(e)?
                        }
                        c if (' '..='~').contains(&c) => c as u16,
                        _ => return None,
                    };
                    // A range, unless the `-` is the class's last character.
                    if self.peek() == Some('-') && self.units.get(self.at + 1) != Some(&u16::from(b']')) {
                        self.at += 1;
                        let c = self.peek()?;
                        self.at += 1;
                        let high = match c {
                            '[' | ']' => return None,
                            '\\' => {
                                let e = self.peek()?;
                                self.at += 1;
                                escaped(e)?
                            }
                            c if (' '..='~').contains(&c) => c as u16,
                            _ => return None,
                        };
                        if high < low {
                            return None;
                        }
                        ranges.push((low, high));
                    } else {
                        ranges.push((low, low));
                    }
                }
                Node::One(Atom::Class(ranges, negated))
            }
            '(' => {
                let group = if self.eat('?') {
                    if !self.eat(':') { return None; }
                    None
                } else {
                    self.groups += 1;
                    Some(self.groups)
                };
                let inner = self.alternatives()?;
                if !self.eat(')') {
                    return None;
                }
                match group { Some(id) => Node::Capture(id, Box::new(inner)), None => inner }
            }
            c if stands_for_itself(c) => Node::One(Atom::Unit(c as u16)),
            _ => return None,
        })
    }

    /// The whole block name, braces included. Every other property stays outside the grammar.
    fn unicode_block(&mut self) -> Option<(u16, u16)> {
        for (name, range) in [("{InBasicLatin}", (0x0000, 0x007f)), ("{InCombiningDiacriticalMarks}", (0x0300, 0x036f))] {
            let end = self.at + name.len();
            if self.units.get(self.at..end).is_some_and(|units| units.iter().copied().eq(name.encode_utf16())) {
                self.at = end;
                return Some(range);
            }
        }
        None
    }

    fn number(&mut self) -> Option<u32> {
        let start = self.at;
        let mut n: u32 = 0;
        while let Some(d) = self.peek().and_then(|c| c.to_digit(10)) {
            n = n.checked_mul(10)?.checked_add(d)?;
            self.at += 1;
        }
        (self.at > start && n <= MOST_REPEATS).then_some(n)
    }

    fn quantified(&mut self, node: Node) -> Option<Node> {
        let (least, most) = match self.peek() {
            Some('*') => (0, None),
            Some('+') => (1, None),
            Some('?') => (0, Some(1)),
            Some('{') => (0, None),
            _ => return Some(node),
        };
        let (least, most) = if self.eat('{') {
            let least = self.number()?;
            let most = if self.eat(',') {
                if self.peek() == Some('}') {
                    None
                } else {
                    Some(self.number()?)
                }
            } else {
                Some(least)
            };
            if !self.eat('}') || most.is_some_and(|m| m < least) {
                return None;
            }
            (least, most)
        } else {
            self.at += 1;
            (least, most)
        };
        // An anchor is not repeated here, nor a quantifier quantified: reluctant, possessive, or stacked.
        if matches!(node, Node::Begin | Node::End) || matches!(self.peek(), Some('*' | '+' | '?' | '{')) {
            return None;
        }
        Some(Node::Repeat(Box::new(node), least, most))
    }
}

/// Whether the ASCII character is itself in a regular expression, with no flag that reads white space or `#`
/// another way: the module's syntax.
fn stands_for_itself(c: char) -> bool {
    c.is_ascii_alphanumeric() || " !\"#%&',-/:;<=>@_`~".contains(c)
}

/// The units that stand for themselves ([`stands_for_itself`]), as the ranges of a class.
fn literal_units() -> Vec<(u16, u16)> {
    let mut ranges: Vec<(u16, u16)> = Vec::new();
    for u in (0u8..128).filter(|u| stands_for_itself(char::from(*u))).map(u16::from) {
        match ranges.last_mut() {
            Some((_, high)) if *high + 1 == u => *high = u,
            _ => ranges.push((u, u)),
        }
    }
    ranges
}

/// The units of `\d`, `\w` and `\s` without `UNICODE_CHARACTER_CLASS`.
fn shorthand(e: char) -> Option<Vec<(u16, u16)>> {
    let range = |lo: char, hi: char| (lo as u16, hi as u16);
    match e {
        'd' => Some(vec![range('0', '9')]),
        'w' => Some(vec![range('a', 'z'), range('A', 'Z'), range('_', '_'), range('0', '9')]),
        's' => Some(vec![range(' ', ' '), (0x09, 0x0D)]),
        _ => None,
    }
}

/// The unit `\` and `e` stand for: a punctuation character itself, or a control character by its letter.
fn escaped(e: char) -> Option<u16> {
    Some(match e {
        't' => 0x09,
        'n' => 0x0A,
        'r' => 0x0D,
        'f' => 0x0C,
        'a' => 0x07,
        'e' => 0x1B,
        e if e.is_ascii_punctuation() => e as u16,
        _ => return None,
    })
}

/// The constant regular expression of these units, in the module's syntax; `None` for any other.
pub fn parse_constant(units: &[u16]) -> Option<Node> {
    let mut reader = Reader { units, at: 0, groups: 0 };
    let node = reader.alternatives()?;
    reader.done().then_some(node)
}

/// Whether `Pattern.compile` of this constant gives a Pattern of pieces ([`Engine::compile_source`]): one in the
/// module's syntax that is more than atoms in sequence. For [`super::gaps::scan`], which counts the call as
/// reproduced where the engine does not meet it as a gap.
pub fn compiles_constant(units: &[u16]) -> bool {
    parse_constant(units).is_some_and(|node| node.flat().is_none())
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
    /// A constant regular expression that is more than atoms in sequence.
    Node(Rc<Node>),
}

impl Kind {
    /// Whether the piece may match a surrogate unit of the input ([`Atom::wide`]). A quoted text matches its own
    /// units, which are looked at where it is matched.
    fn wide(&self) -> bool {
        match self {
            Kind::One(atom) | Kind::Star(atom) => atom.wide(),
            Kind::Text(..) => false,
            Kind::Parts(_, between) => between.iter().any(|(atom, _)| atom.wide()),
            Kind::Node(node) => node.wide(),
        }
    }
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
    Pattern(Vec<Piece>, Flags),
    Matcher(Vec<Piece>, Flags, Text),
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
    matches!((name, descriptor), ("split", "(Ljava/lang/String;I)[Ljava/lang/String;") | ("matches", "(Ljava/lang/String;)Z"))
}

/// Whether the engine models the static call here, where its arguments let it.
pub fn models_static(owner: &str, name: &str, descriptor: &str) -> bool {
    matches!(
        (owner, name, descriptor),
        (PATTERN, "quote", "(Ljava/lang/String;)Ljava/lang/String;") | (PATTERN, "compile", "(Ljava/lang/String;I)Ljava/util/regex/Pattern;") | (STRING, "join", "(Ljava/lang/CharSequence;[Ljava/lang/CharSequence;)Ljava/lang/String;")
    )
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
        let node = parse_constant(&units)?;
        Some(match node.flat() {
            Some(atoms) => atoms.into_iter().map(|(atom, starred)| Piece { when: TRUE, kind: if starred { Kind::Star(atom) } else { Kind::One(atom) } }).collect(),
            None => vec![Piece { when: TRUE, kind: Kind::Node(Rc::new(node)) }],
        })
    }

    /// `String.matches(regex)` on a String of content `s`: see the module's notes. `None` where the call stays
    /// the JDK's.
    pub(super) fn string_matches(&mut self, path: &mut Path, s: &Array, args: &[Val]) -> Option<Step> {
        let [Val::R(regex)] = args else { return None };
        let Some(regex) = *regex else { return Some(self.raise(path, "java/lang/NullPointerException")) };
        let pieces = self.regex_source(path, regex).filter(|_| path.objects[regex].regex.is_none())?;
        let (truth, surrogate) = self.matches(&pieces, NO_FLAGS, &Text::of(s));
        Some(self.branch_gap_or(path, surrogate, (GapKind::JdkPrimitiveMethod, STRING, "matches", "(Ljava/lang/String;)Z"), move |engine, path| engine.push_truth(path, truth)))
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
                if path.objects[elements].given {
                    if let Err(stop) = self.reads(path, || "reads an array that was there before the call (join)".into()) {
                        return Some(Err(stop));
                    }
                }
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
                let flags = match self.flags(path, flags) {
                    Ok(flags) => flags?,
                    Err(stop) => return Some(Err(stop)),
                };
                let pieces = match self.regex_source(path, regex) {
                    Some(pieces) => pieces,
                    None => match self.literal_then_any(path, regex) {
                        Ok(pieces) => pieces?,
                        Err(stop) => return Some(Err(stop)),
                    },
                };
                self.regex_object(path, PATTERN, Regex::Pattern(pieces, flags))
            }
            _ => return None,
        };
        self.push(path, Val::R(Some(value)));
        self.advance(path);
        Some(Ok(None))
    }

    /// The flags of a `Pattern.compile`, where no bit but `CASE_INSENSITIVE`'s and `DOTALL`'s can be set on the path
    /// (the solver's to show where the argument is no constant); `None` where another can.
    fn flags(&mut self, path: &Path, flags: &Bits) -> Result<Option<Flags>, Stop> {
        let others: Vec<Lit> = flags.iter().enumerate().filter(|(bit, _)| ![CASE_INSENSITIVE, DOTALL].contains(bit)).map(|(_, &l)| l).collect();
        let other = self.any(&others);
        if other != FALSE {
            let mut assumptions = path.cond.clone();
            assumptions.push(other);
            if self.solve(&assumptions)? {
                return Ok(None);
            }
        }
        Ok(Some(Flags { insensitive: flags[CASE_INSENSITIVE], dotall: flags[DOTALL] }))
    }

    /// The pieces of the String `o`, whose content the engine holds and which is no constant, where every content
    /// it can have on the path is characters that stand for themselves followed by `.*`: those characters as a
    /// quoted text (the String's units, two fewer), then `.` any number of times. The solver shows it of the path,
    /// so the rule takes nothing on trust of the String; `None` where it finds any other content, or holds none.
    fn literal_then_any(&mut self, path: &Path, o: usize) -> Result<Option<Vec<Piece>>, Stop> {
        let Some(s) = path.objects[o].content().cloned() else { return Ok(None) };
        let (two, literal) = (self.b.constant(2, 32), Atom::Class(literal_units(), false));
        let (dot, star) = (self.b.constant(i64::from(b'.'), 16), self.b.constant(i64::from(b'*'), 16));
        // Where the String is anything else: shorter than `.*`, or a unit that is not what its place asks for.
        let mut other = vec![self.b.slt(&s.length, &two)];
        for (i, cell) in s.cells.iter().enumerate() {
            let places: [(i64, Lit); 3] = [(i as i64 + 2, self.b.eq(cell, &dot)), (i as i64 + 1, self.b.eq(cell, &star)), (0, self.atom_matches(&literal, NO_FLAGS, cell, cell))];
            for (k, (length, fits)) in places.into_iter().enumerate() {
                let length = self.b.constant(length, 32);
                // The unit is the `.` or the `*` of a String of exactly this length, or a character of a longer one.
                let here = if k < 2 {
                    self.b.eq(&s.length, &length)
                } else {
                    let after = self.b.constant(i as i64 + 2, 32);
                    self.b.slt(&after, &s.length)
                };
                other.push(self.b.and(here, -fits));
            }
        }
        let other = self.any(&other);
        if other != FALSE {
            let mut assumptions = path.cond.clone();
            assumptions.push(other);
            if self.solve(&assumptions)? {
                return Ok(None);
            }
        }
        let text = Text { length: self.b.sub(&s.length, &two), cells: s.cells };
        Ok(Some(vec![Piece { when: TRUE, kind: Kind::Text(text, None) }, Piece { when: TRUE, kind: Kind::Star(Atom::Any) }]))
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

    /// `Pattern.compile(String)` of the String `o` that is a regular expression by its tag, or a constant in the
    /// module's syntax that is more than atoms in sequence: a Pattern of its pieces. `None` for any other String.
    pub(super) fn compile_source(&mut self, path: &mut Path, o: usize) -> Option<Step> {
        let pieces = match path.objects[o].regex.as_deref() {
            Some(Regex::Source(pieces)) => pieces.clone(),
            Some(_) => return None,
            // A constant with a class, a group, an alternative or a counted quantifier: one the plain form
            // ([`crate::jdk_facts::plain_regex`]) leaves out, or says nothing of the matching of.
            None => self.regex_source(path, o).filter(|pieces| pieces.iter().any(|piece| matches!(piece.kind, Kind::Node(_))))?,
        };
        let pattern = self.regex_object(path, PATTERN, Regex::Pattern(pieces, NO_FLAGS));
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
                path.objects[matcher].fields.insert(MATCH_INPUT.into(), Val::R(Some(input)));
                path.objects[matcher].fields.insert(MATCH_SUCCESS.into(), Val::I(self.b.constant(0, 32)));
                self.push(path, Val::R(Some(matcher)));
                self.advance(path);
                Some(Ok(None))
            }
            (Regex::Matcher(pieces, flags, input), "matches", "()Z", []) => {
                let (truth, surrogate) = self.matches(&pieces, flags, &input);
                if let Err(stop) = self.keeps(path, Some(o), "updates a pre-existing Matcher's match state") { return Some(Err(stop)); }
                Some(self.branch_gap_or(path, surrogate, (GapKind::JdkReferenceMethod, MATCHER, name, descriptor), move |engine, path| {
                    let flag = engine.b.zext(&vec![truth], 32);
                    path.objects[o].fields.insert(MATCH_SUCCESS.into(), Val::I(flag));
                    engine.push_truth(path, truth);
                }))
            }
            (Regex::Matcher(pieces, _, _), "group", "(I)Ljava/lang/String;", [Val::I(index)]) => {
                Some(self.matched_group(path, o, &pieces, self.b.constant_value(index)))
            }
            (Regex::Matcher(pieces, _, _), "group", "()Ljava/lang/String;", []) => Some(self.matched_group(path, o, &pieces, Some(0))),
            (Regex::Matcher(..), _, _, _) => {
                // Any other method may change what the Matcher matches (its region, its input, its pattern).
                path.objects[o].regex = None;
                None
            }
            _ => None,
        }
    }

    fn matched_group(&mut self, path: &mut Path, o: usize, pieces: &[Piece], index: Option<i64>) -> Step {
        self.reads_field(path, o, MATCHER, "first", "I")?;
        let Some(Val::I(flag)) = path.objects[o].fields.get(MATCH_SUCCESS) else { return unsupported("Matcher.group without a recorded match attempt") };
        let failed = self.b.is_zero(flag);
        // The JDK checks for a preceding successful match before it validates the index.
        if failed != FALSE && !path.cond.contains(&-failed) {
            let mut successful = path.cond.clone();
            successful.push(-failed);
            if failed == TRUE || !self.solve(&successful)? { return self.raise(path, "java/lang/IllegalStateException"); }
        }
        let Some(index) = index else { return unsupported("Matcher.group with a symbolic group number") };
        let node = match pieces {
            [Piece { when: TRUE, kind: Kind::Node(node) }] => Some(node),
            _ => None,
        };
        if index > 0 && node.is_none() && pieces.iter().any(|p| matches!(p.kind, Kind::Node(_))) {
            return unsupported("Matcher.group numbering in a composed pattern");
        }
        if index < 0 || index as usize > node.map_or(0, |n| n.last_group()) {
            let mut invalid = Ok(None);
            let status = self.branch_throw_or(path, failed, "java/lang/IllegalStateException", |engine, side| {
                invalid = engine.raise(side, "java/lang/IndexOutOfBoundsException");
            });
            return invalid.and(status);
        }
        let Some(Val::R(Some(source))) = path.objects[o].fields.get(MATCH_INPUT).cloned() else {
            return unsupported("Matcher.group on a choice of input String identities");
        };
        let value = if index == 0 {
            Val::R(Some(source))
        } else {
            let Some((start, end)) = node.and_then(|n| n.capture(index as usize, Some(0), Some(0))) else {
                return unsupported(format!("Matcher.group({index}) has an optional, repeated, or variable capture without two determined boundaries"));
            };
            let input = path.objects[source].content().expect("matcher on a String").clone();
            let begin = start.resolve(&mut self.b, &input.length);
            let end = end.resolve(&mut self.b, &input.length);
            self.range(path, &input, &begin, &end, Some(source))
        };
        self.branch_throw(path, failed, "java/lang/IllegalStateException", value)
    }

    /// Whether `pieces`, under `flags`, match the whole of `input`, and whether a surrogate is among the units
    /// compared (where matching by unit is not the JDK's matching by code point).
    fn matches(&mut self, pieces: &[Piece], flags: Flags, input: &Text) -> (Lit, Lit) {
        let insensitive = flags.insensitive;
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
        // `.*` at the end takes the rest of the input by unit as it does by code point (the module's notes).
        let ends_with_any = matches!(pieces.last(), Some(Piece { kind: Kind::Star(Atom::Any), .. }));
        if pieces[..pieces.len() - usize::from(ends_with_any)].iter().any(|piece| piece.when != FALSE && piece.kind.wide()) {
            inside_surrogates(self, input, TRUE, &mut surrogates);
        }
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
                Kind::Node(node) => self.node_step(&reach, node, flags, input, &units),
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

    /// The unit as two units are compared: itself, or, where ASCII case is ignored, an ASCII upper-case letter
    /// lowered (the formula `String.toLowerCase()`'s model makes of the unit, [`Engine::lowered_ascii`]).
    fn folded(&mut self, unit: &Bits, insensitive: Lit) -> Bits {
        if insensitive == FALSE {
            return unit.clone();
        }
        let lowered = self.lowered_ascii(unit).1;
        self.b.ite_bits(insensitive, &lowered, unit)
    }

    /// The positions the pieces so far and then `node` reach, from those `reach`ed.
    fn node_step(&mut self, reach: &[Lit], node: &Node, flags: Flags, input: &Text, units: &[Bits]) -> Vec<Lit> {
        let either = |engine: &mut Self, a: &[Lit], b: &[Lit]| -> Vec<Lit> { a.iter().zip(b).map(|(x, y)| engine.b.or(*x, *y)).collect() };
        match node {
            Node::One(atom) => self.atom_step(reach, atom, false, flags, input, units),
            Node::Capture(_, body) => self.node_step(reach, body, flags, input, units),
            Node::Seq(nodes) => nodes.iter().fold(reach.to_vec(), |reach, node| self.node_step(&reach, node, flags, input, units)),
            Node::Alt(nodes) => {
                let mut any = vec![FALSE; reach.len()];
                for node in nodes {
                    let one = self.node_step(reach, node, flags, input, units);
                    any = either(self, &any, &one);
                }
                any
            }
            Node::Repeat(inner, least, most) => {
                let mut reached = reach.to_vec();
                for _ in 0..*least {
                    reached = self.node_step(&reached, inner, flags, input, units);
                }
                match (most, &**inner) {
                    (Some(most), _) => {
                        let mut any = reached.clone();
                        for _ in *least..*most {
                            reached = self.node_step(&reached, inner, flags, input, units);
                            any = either(self, &any, &reached);
                        }
                        any
                    }
                    (None, Node::One(atom)) => self.atom_step(&reached, atom, true, flags, input, units),
                    // Each further time either adds nothing or takes a unit more: as many times as there are units.
                    (None, _) => {
                        let mut any = reached.clone();
                        for _ in 0..units.len() {
                            reached = self.node_step(&reached, inner, flags, input, units);
                            if reached.iter().all(|&l| l == FALSE) {
                                break;
                            }
                            any = either(self, &any, &reached);
                        }
                        any
                    }
                }
            }
            Node::Begin => reach.iter().enumerate().map(|(j, &l)| if j == 0 { l } else { FALSE }).collect(),
            Node::End => reach
                .iter()
                .enumerate()
                .map(|(j, &l)| {
                    let here = self.b.constant(j as i64, 32);
                    let is_end = self.b.eq(&input.length, &here);
                    self.b.and(l, is_end)
                })
                .collect(),
        }
    }

    /// The positions the pieces so far and then `atom` reach, from those `reach`ed: once, or any number of times.
    fn atom_step(&mut self, reach: &[Lit], atom: &Atom, starred: bool, flags: Flags, input: &Text, units: &[Bits]) -> Vec<Lit> {
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

    fn class_contains(&mut self, ranges: &[(u16, u16)], raw: &Bits) -> Lit {
        let mut found = FALSE;
        for &(lo, hi) in ranges {
            let low = self.b.constant(i64::from(lo), 16);
            let inside = if lo == hi {
                self.b.eq(raw, &low)
            } else {
                let high = self.b.constant(i64::from(hi), 16);
                let below = self.b.ult(raw, &low);
                let above = self.b.ult(&high, raw);
                self.b.and(-below, -above)
            };
            found = self.b.or(found, inside);
        }
        found
    }

    /// Whether `atom` matches the input unit `raw`, which is `unit` as units are compared.
    fn atom_matches(&mut self, atom: &Atom, flags: Flags, raw: &Bits, unit: &Bits) -> Lit {
        match atom {
            // An upper-case letter is compared lowered where the input's units are ([`Engine::folded`]).
            Atom::Unit(u) => {
                let exact = self.b.constant(i64::from(*u), 16);
                let constant = if (u16::from(b'A')..=u16::from(b'Z')).contains(u) {
                    let lowered = self.b.constant(i64::from(u | 0x20), 16);
                    self.b.ite_bits(flags.insensitive, &lowered, &exact)
                } else {
                    exact
                };
                self.b.eq(unit, &constant)
            }
            Atom::Class(ranges, negated) => {
                let mut is = self.class_contains(ranges, raw);
                if flags.insensitive != FALSE {
                    // Without UNICODE_CASE, Pattern.CIRange adds just the other spelling of an ASCII letter.
                    // When the flag is set, `unit` is lower-cased already. Flip bit 5 only for those letters.
                    let letter = self.class_contains(&[(u16::from(b'a'), u16::from(b'z'))], unit);
                    let fold = self.b.and(flags.insensitive, letter);
                    let mut other = raw.clone();
                    other[5] = -other[5];
                    let alternate = self.class_contains(ranges, &other);
                    let included = self.b.and(fold, alternate);
                    is = self.b.or(is, included);
                }
                if *negated {
                    -is
                } else {
                    is
                }
            }
            Atom::Any if flags.dotall == TRUE => TRUE,
            Atom::Any => {
                let terminators: Vec<Lit> = [0x0A, 0x0D, 0x85, 0x2028, 0x2029]
                    .into_iter()
                    .map(|t| {
                        let constant = self.b.constant(t, 16);
                        self.b.eq(raw, &constant)
                    })
                    .collect();
                let terminator = self.any(&terminators);
                self.b.or(flags.dotall, -terminator)
            }
        }
    }
}
