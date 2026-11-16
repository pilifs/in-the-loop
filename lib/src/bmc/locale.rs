//! The default locale, as far as it decides how a String's case is lowered.
//!
//! `String.toLowerCase()` reads `Locale.getDefault()`, which a program may set, and `toLowerCase(Locale)` is told a
//! locale. Of all the JDK's locales only three change how an ASCII letter is lowered: Turkish and Azeri (`tr`,
//! `az`) lower `I` to U+0131, the dotless i, and Lithuanian (`lt`) adds a dot above to `I` and `J` before a
//! combining accent, which no ASCII String holds. So on a String whose units are all ASCII the answer depends on
//! one fact about the locale: whether its language is `tr` or `az` (`java.lang.String`, `StringLatin1.toLowerCase`
//! and `ConditionalSpecialCasing` of JDK 25; spring-framework's CVE-2024-38820 is a deny list read under such a
//! default). The engine holds that fact of a Locale where it can know it, and the locale is then an input of a
//! check like any other: a symbolic reference among Locales makes the lowering a formula of its guards, and no
//! path is split for it.
//!
//! - `getstatic` of one of `java.util.Locale`'s constants (`ROOT`, `ENGLISH`, `US` and the other nineteen): one
//!   object for the run, as it is on a JVM. None of them is Turkish or Azeri.
//! - `Locale.forLanguageTag(String)` of a constant tag of the plain form, a language of two or three ASCII letters,
//!   then optionally a script of four letters, then optionally a region of two letters or three digits
//!   (`tr-TR`, `az-Latn-AZ`, `en`): a Locale whose language is the first subtag in lower case. The JDK maps no
//!   three-letter code to `tr` or `az`, so `tur` is not Turkish to `toLowerCase`. `NullPointerException` for null.
//!   Any other tag (a variant, an extension, a grandfathered tag, a private use one, one that is no constant) is
//!   the JDK call it was. Each call gives an object of its own, and whether two Locales are one object is not
//!   the engine's to say (the JDK caches them, and returns its constants for their tags): a comparison of two
//!   Locales by reference is refused by name unless they are one object to the engine.
//! - `Locale.setDefault(Locale)`: the default from then on, on the path; `NullPointerException` for null. A
//!   Locale the engine does not hold the fact of (one a JDK call it does not model returned) can be set, and a
//!   `toLowerCase()` under it is the JDK call it was.
//! - `String.toLowerCase()`: lowered under the default the path set last, and where it set none, under the JVM's
//!   own, which the run assumes is none of the three and says so ([`super::strings::LOCALE_ASSUMPTION`]).
//! - `String.toLowerCase(Locale)`: lowered under that Locale; `NullPointerException` for null.
//!
//! `Locale.getDefault()`, `setDefault(Locale.Category, Locale)` (which does not change what `toLowerCase()` reads)
//! and every method of a Locale stay the JDK calls they were. A String with a unit outside ASCII is lowered by
//! Unicode's tables, its context and the locale's own rules, which the engine has not: there both calls are the gap
//! they were, whatever the locale.

use super::*;

pub const LOCALE: &str = "java/util/Locale";

/// The static fields of `java.util.Locale` that are Locales (its Javadoc, JDK 25): the root locale, nine languages
/// and twelve countries, none of them Turkish, Azeri or Lithuanian.
pub const CONSTANTS: [&str; 22] = [
    "ROOT", "ENGLISH", "FRENCH", "GERMAN", "ITALIAN", "JAPANESE", "KOREAN", "CHINESE", "SIMPLIFIED_CHINESE", "TRADITIONAL_CHINESE", "FRANCE", "GERMANY", "ITALY", "JAPAN", "KOREA", "UK", "US", "CANADA", "CANADA_FRENCH", "CHINA", "PRC", "TAIWAN",
];

/// The field of a Locale's object that holds what the engine knows of it: 1 where its language is `tr` or `az`,
/// 0 where it is any other. A Locale without it is one the engine knows nothing of.
const DOTLESS: &str = "\u{3bb}dotless";

/// The static "field" that holds the default locale a path set, beside the application's static fields.
const DEFAULT: &str = "\u{3bb}default";

/// Whether `declaring.name` is one of `Locale`'s constants, which the engine reads ([`CONSTANTS`]).
pub fn constant(declaring: &str, name: &str) -> bool {
    declaring == LOCALE && CONSTANTS.contains(&name)
}

/// Whether the engine models the static call here, where its arguments let it.
pub fn models_static(owner: &str, name: &str, descriptor: &str) -> bool {
    matches!((owner, name, descriptor), (LOCALE, "forLanguageTag", "(Ljava/lang/String;)Ljava/util/Locale;") | (LOCALE, "setDefault", "(Ljava/util/Locale;)V"))
}

/// Whether the static call takes a symbolic reference as it is ([`Choice`]): the default locale is stored, not read.
pub fn takes_a_choice(owner: &str, name: &str, descriptor: &str) -> bool {
    (owner, name, descriptor) == (LOCALE, "setDefault", "(Ljava/util/Locale;)V")
}

/// Whether the engine models `String.name(descriptor)` here.
pub fn models_string(name: &str, descriptor: &str) -> bool {
    (name, descriptor) == ("toLowerCase", "(Ljava/util/Locale;)Ljava/lang/String;")
}

/// The language of a language tag of the plain form, in lower case: see the module's notes. `None` for any other
/// tag.
pub fn plain_tag_language(units: &[u16]) -> Option<String> {
    let text = String::from_utf16(units).ok()?;
    let mut parts = text.split('-');
    let letters = |s: &str, n: std::ops::RangeInclusive<usize>| n.contains(&s.len()) && s.bytes().all(|b| b.is_ascii_alphabetic());
    let language = parts.next().filter(|s| letters(s, 2..=3))?;
    let region = |s: &str| letters(s, 2..=2) || (s.len() == 3 && s.bytes().all(|b| b.is_ascii_digit()));
    let rest: Vec<&str> = parts.collect();
    let plain = match rest.as_slice() {
        [] => true,
        [one] => letters(one, 4..=4) || region(one),
        [script, r] => letters(script, 4..=4) && region(r),
        _ => false,
    };
    plain.then(|| language.to_ascii_lowercase())
}

impl Engine<'_> {
    /// A Locale of which the engine knows whether its language is `tr` or `az`.
    fn known_locale(&mut self, path: &mut Path, o: usize, dotless: bool) {
        let fact = self.b.constant(i64::from(dotless), 32);
        path.objects[o].fields.insert(DOTLESS.to_string(), Val::I(fact));
    }

    /// The object of one of `Locale`'s constants ([`CONSTANTS`]).
    pub(super) fn locale_constant(&mut self, path: &mut Path, name: &str) -> usize {
        let fresh = !path.literals.contains_key(&Literal::Locale(name.to_string()));
        let o = self.literal(path, Literal::Locale(name.to_string()), LOCALE);
        if fresh {
            self.known_locale(path, o, false);
        }
        o
    }

    /// Whether the object is a Locale the engine knows the fact of ([`DOTLESS`]).
    pub(super) fn is_known_locale(path: &Path, o: usize) -> bool {
        path.objects[o].class == LOCALE && path.objects[o].fields.contains_key(DOTLESS)
    }

    /// Whether the locale `value` is lowers `I` to the dotless i, as a literal, and whether it is null: `None` where
    /// it may be a Locale the engine knows nothing of, or is no reference.
    fn dotless(&mut self, path: &Path, value: &Val) -> Option<(Lit, Lit)> {
        let (mut dotless, mut null) = (FALSE, FALSE);
        for (g, t) in value.options()? {
            match t {
                None => null = self.b.or(null, g),
                Some(o) => {
                    let Some(Val::I(fact)) = path.objects[o].fields.get(DOTLESS).filter(|_| path.objects[o].class == LOCALE).cloned() else { return None };
                    if self.b.constant_value(&fact)? != 0 {
                        dotless = self.b.or(dotless, g);
                    }
                }
            }
        }
        Some((dotless, null))
    }

    /// Whether `String.toLowerCase()` lowers `I` to the dotless i on this path, by the default locale it set last:
    /// `FALSE` under the stated assumption where it set none ([`strings::LOCALE_ASSUMPTION`]), `None` where the
    /// default is a Locale the engine knows nothing of.
    pub(super) fn default_dotless(&mut self, path: &Path) -> Option<Lit> {
        match path.statics.get(&(LOCALE.to_string(), DEFAULT.to_string())).cloned() {
            None => {
                self.assumed.insert(strings::LOCALE_ASSUMPTION.to_string());
                Some(FALSE)
            }
            // `setDefault` throws for null, so the default is never null.
            Some(value) => self.dotless(path, &value).map(|(dotless, _)| dotless),
        }
    }

    /// Whether `String.toLowerCase(locale)` lowers `I` to the dotless i, where `locale` is a known reference to a
    /// Locale the engine knows the fact of.
    pub(super) fn argument_dotless(&mut self, path: &Path, locale: usize) -> Option<Lit> {
        self.dotless(path, &Val::R(Some(locale))).map(|(dotless, _)| dotless)
    }

    /// `Locale.forLanguageTag(tag)` and `Locale.setDefault(locale)`: see the module's notes. `None` where the call
    /// stays the JDK's.
    pub(super) fn locale_static(&mut self, path: &mut Path, name: &str, args: &[Val]) -> Option<Step> {
        match (name, args) {
            ("forLanguageTag", [Val::R(tag)]) => {
                let Some(tag) = *tag else { return Some(self.raise(path, "java/lang/NullPointerException")) };
                let language = plain_tag_language(&self.constant_units(path, tag)?)?;
                let o = self.alloc(path, LOCALE);
                self.known_locale(path, o, matches!(language.as_str(), "tr" | "az"));
                self.push(path, Val::R(Some(o)));
                self.advance(path);
                Some(Ok(None))
            }
            ("setDefault", [locale]) => {
                let options = locale.options()?;
                let mut null = FALSE;
                for (g, t) in &options {
                    if t.is_none() {
                        null = self.b.or(null, *g);
                    }
                }
                if let Err(stop) = self.keeps(path, None, "sets the default locale") {
                    return Some(Err(stop));
                }
                let locale = locale.clone();
                Some(self.branch_throw_or(path, null, "java/lang/NullPointerException", move |engine, path| {
                    path.statics.insert((LOCALE.to_string(), DEFAULT.to_string()), locale);
                    engine.advance(path);
                }))
            }
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn language(tag: &str) -> Option<String> {
        plain_tag_language(&tag.encode_utf16().collect::<Vec<u16>>())
    }

    /// The plain form of a language tag: a language, then optionally a script, then optionally a region. Anything
    /// the JDK's parser would read otherwise (a grandfathered tag, an extended language, a variant, an extension,
    /// private use, an ill-formed tag) is not taken.
    #[test]
    fn a_plain_language_tag_gives_its_language_in_lower_case_and_no_other_tag_is_taken() {
        for (tag, expected) in [("tr-TR", "tr"), ("az-AZ", "az"), ("AZ-Latn-az", "az"), ("en-US", "en"), ("lt-LT", "lt"), ("TR", "tr"), ("tur", "tur"), ("es-419", "es"), ("az-Cyrl", "az"), ("und", "und")] {
            assert_eq!(language(tag).as_deref(), Some(expected), "{tag}");
        }
        for tag in ["", "i-klingon", "art-lojban", "zh-min-nan", "zh-yue", "de-DE-1996", "tr-TR-u-co-phonebk", "x-private", "t", "abcd", "tr_TR", "tr-", "tr-T", "tr-TR-TR", "en-US-POSIX", "tr-\u{130}R"] {
            assert_eq!(language(tag), None, "{tag}");
        }
    }
}
