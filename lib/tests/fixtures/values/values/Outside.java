package values;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.regex.Pattern;

/**
 * Harness-shaped checks that each reach one operation outside the values models (lib/tests/values.rs, V3's strict
 * gap detection): a String method other than the six the own checker models on content, a list method or form
 * that no evidence record of values::OPERATIONS samples, although the list models implement it, a map the HashMap
 * model is not, a method it has not or a key it can't hash, and a regular expression that is not a plain constant.
 * Each claim holds on
 * the JVM (ValuesRunner runs each method there and must see it return), so that a verdict could only come from
 * semantics the records don't vouch for: under the strict engine every one must end with the operation as a named
 * gap, and no verdict.
 */
public final class Outside {
    private Outside() {
    }

    /** An element: a mutable application object. */
    static final class Item {
        int value;

        Item(int value) {
            this.value = value;
        }
    }

    // java.lang.String: a method no record of values::OPERATIONS samples.

    public static void upper(String s) {
        if (s != null && s.toUpperCase().length() < 0) {
            throw new AssertionError();
        }
    }

    public static void replace(String s) {
        if (s != null && s.replace('a', 'b').length() != s.length()) {
            throw new AssertionError();
        }
    }

    /** A language tag with a variant is the JDK's parser's to read. */
    public static void localeOfAVariantTag(String s) {
        if (s != null && java.util.Locale.forLanguageTag("de-DE-1996") == null) {
            throw new AssertionError();
        }
    }

    public static void defaultLocale(String s) {
        if (s != null && java.util.Locale.getDefault() == null) {
            throw new AssertionError();
        }
    }

    public static void strip(String s) {
        if (s != null && s.strip().length() > s.length()) {
            throw new AssertionError();
        }
    }

    public static void compareTo(String s) {
        if (s != null && s.compareTo(s) != 0) {
            throw new AssertionError();
        }
    }

    /** subSequence called through CharSequence. */
    public static void subSequence(String s) {
        CharSequence c = s;
        if (s != null && c.subSequence(0, 0).length() != 0) {
            throw new AssertionError();
        }
    }

    public static void valueOf(int n) {
        if (String.valueOf(n).isEmpty()) {
            throw new AssertionError();
        }
    }

    // java.util.List: what the models implement but no record samples.

    public static void contains(int v) {
        Item x = new Item(v);
        if (!List.of(x, new Item(v)).contains(x)) {
            throw new AssertionError();
        }
    }

    public static void indexOfElement(int v) {
        Item x = new Item(v);
        if (List.of(new Item(v), x).indexOf(x) != 1) {
            throw new AssertionError();
        }
    }

    public static void lastIndexOf(int v) {
        Item x = new Item(v);
        if (List.of(x, x, new Item(v)).lastIndexOf(x) != 1) {
            throw new AssertionError();
        }
    }

    public static void equalLists(int v) {
        Item x = new Item(v);
        if (!List.of(x).equals(List.of(x))) {
            throw new AssertionError();
        }
    }

    /** The empty list's hash code, 1, which reads no element's. */
    public static void emptyHashCode(int v) {
        if (List.of().hashCode() != 1) {
            throw new AssertionError();
        }
    }

    /** hashCode called through Object, on a list. */
    public static void hashCodeAsObject(int v) {
        Object o = List.of();
        if (o.hashCode() != 1) {
            throw new AssertionError();
        }
    }

    public static void toArray(int v) {
        if (List.of(new Item(v)).toArray().length != 1) {
            throw new AssertionError();
        }
    }

    /** A change no record samples, which the models refuse as the JDK does. */
    public static void addAll(int v) {
        try {
            List.of(new Item(v)).addAll(List.of(new Item(v)));
        } catch (UnsupportedOperationException e) {
            return;
        }
        throw new AssertionError();
    }

    public static void removeElement(int v) {
        Item x = new Item(v);
        try {
            List.of(x).remove(x);
        } catch (UnsupportedOperationException e) {
            return;
        }
        throw new AssertionError();
    }

    public static void sort(int v) {
        try {
            List.of(new Item(v), new Item(v)).sort(null);
        } catch (UnsupportedOperationException e) {
            return;
        }
        throw new AssertionError();
    }

    /** List.of's array form, given an array. */
    public static void arrayForm(int v) {
        Item[] items = {new Item(v)};
        if (List.of(items).size() != 1) {
            throw new AssertionError();
        }
    }

    /** List.of's array form, as javac calls it for more than ten elements. */
    public static void elevenElements(int v) {
        Item x = new Item(v);
        if (List.of(x, x, x, x, x, x, x, x, x, x, x).size() != 11) {
            throw new AssertionError();
        }
    }

    // java.util.HashMap: what the model has not, is not, or can't hash.

    public static void mapRemove(String s) {
        Map<String, String> m = new HashMap<>();
        m.put(s, s);
        if (m.remove(s) != s) {
            throw new AssertionError();
        }
    }

    /** A default method of java.util.Map, which the model doesn't override: the JDK's. */
    public static void mapGetOrDefault(String s) {
        Map<String, String> m = new HashMap<>();
        if (m.getOrDefault(s, s) != s) {
            throw new AssertionError();
        }
    }

    /** A fresh key with Object's native hashCode; its stable identity hash requires the JDK image. */
    public static void mapKeyOfIdentity(int v) {
        Map<Item, Item> m = new HashMap<>();
        Item key = new Item(v);
        m.put(key, key);
        if (m.get(key) != key) {
            throw new AssertionError();
        }
    }

    public static void linkedMap(String s) {
        Map<String, String> m = new LinkedHashMap<>(new HashMap<String, String>());
        if (!m.isEmpty()) {
            throw new AssertionError();
        }
    }

    public static void mapOfAMap(String s) {
        Map<String, String> m = new HashMap<>(new HashMap<String, String>());
        if (!m.isEmpty()) {
            throw new AssertionError();
        }
    }

    // java.util.regex.Pattern and java.util.Objects: all but compile of a constant of the plain form or the checker's
    // syntax, matcher(..).matches() on one of the latter, and requireNonNull.

    /** A reluctant quantifier: outside the plain form and the checker's own syntax (bmc/regex.rs). */
    public static void patternOutsideTheSyntax(String s) {
        if (Pattern.compile("[a-z]+?") == null) {
            throw new AssertionError();
        }
    }

    public static void patternOfAnInput(String s) {
        if (s != null && s.equals("ab") && Pattern.compile(s) == null) {
            throw new AssertionError();
        }
    }

    /** A Pattern's methods but matcher: its matcher(..).matches() is the checker's (values.Operations.patternMatches). */
    public static void patternsPattern(String s) {
        if (s != null && Pattern.compile("a+").pattern() == null) {
            throw new AssertionError();
        }
    }

    public static void requireNonNullElse(String s) {
        if (Objects.requireNonNullElse(s, "") == null) {
            throw new AssertionError();
        }
    }
}
