package values;

import java.util.List;

/**
 * Harness-shaped checks that each reach one operation outside the values models (lib/tests/values.rs, V3's strict
 * gap detection): a String method other than the five the own checker models on content, and a list method or form
 * that no evidence record of values::OPERATIONS samples, although the list models implement it. Each claim holds on
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

    // java.lang.String: every method but length, isEmpty, charAt, equals and startsWith.

    public static void upper(String s) {
        if (s != null && s.toUpperCase().length() < 0) {
            throw new AssertionError();
        }
    }

    public static void indexOf(String s) {
        if (s != null && s.indexOf('a') >= s.length()) {
            throw new AssertionError();
        }
    }

    public static void hashCodeOf(String s) {
        if (s != null && s.isEmpty() && s.hashCode() != 0) {
            throw new AssertionError();
        }
    }

    public static void substring(String s) {
        if (s != null && s.substring(0).length() != s.length()) {
            throw new AssertionError();
        }
    }

    public static void compareTo(String s) {
        if (s != null && s.compareTo(s) != 0) {
            throw new AssertionError();
        }
    }

    /** equals called through Object, not String: the JDK's Object.equals as the bytecode names it. */
    public static void equalsAsObject(String s) {
        Object o = s;
        if (s != null && !o.equals(s)) {
            throw new AssertionError();
        }
    }

    /** length called through CharSequence. */
    public static void lengthAsCharSequence(String s) {
        CharSequence c = s;
        if (s != null && c.length() != s.length()) {
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
}
