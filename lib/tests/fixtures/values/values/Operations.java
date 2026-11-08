package values;

import java.util.Iterator;
import java.util.List;

/**
 * The boundary cases of every operation the values models implement (lib/tests/values.rs,
 * values::operations): each static method calls one operation on values made from its int arguments, and the test
 * runs it on the JVM, in the interpreter and in the own checker (through a generated method asserting the JVM's
 * outcome), which must all agree. Each operation's evidence record names the methods that sample it, and the
 * exceptions they were seen to throw.
 *
 * A String is made at run time by concatenating chars (never a literal with an isolated surrogate, which the class
 * reader decodes lossily), and a list by List.of over items made by their constructor.
 */
public final class Operations {
    private Operations() {
    }

    /** The first n of the code units a, b, c as a fresh String, or null for a negative n. */
    static String of(int n, int a, int b, int c) {
        if (n < 0) {
            return null;
        }
        switch (n) {
            case 0:
                return "";
            case 1:
                return "" + (char) a;
            case 2:
                return "" + (char) a + (char) b;
            default:
                return "" + (char) a + (char) b + (char) c;
        }
    }

    // java.lang.String

    static int length(int n, int a, int b, int c) {
        return of(n, a, b, c).length();
    }

    static boolean isEmpty(int n, int a, int b, int c) {
        return of(n, a, b, c).isEmpty();
    }

    static int charAt(int n, int a, int b, int c, int i) {
        return of(n, a, b, c).charAt(i);
    }

    /** One String's content against another's: either may be null (the receiver's a NullPointerException). */
    static boolean equalsContent(int n, int a, int b, int c, int m, int d, int e, int f) {
        return of(n, a, b, c).equals(of(m, d, e, f));
    }

    static boolean equalsItself(int n, int a, int b, int c) {
        String s = of(n, a, b, c);
        return s.equals(s);
    }

    static boolean equalsAnotherClass(int n, int a, int b, int c) {
        return of(n, a, b, c).equals(new Object());
    }

    /** Equal content, two objects: equal, and not the same reference. */
    static boolean equalNotSame(int n, int a, int b, int c) {
        String s = of(n, a, b, c);
        String t = of(n, a, b, c);
        return s.equals(t) && s != t;
    }

    static boolean startsWith(int n, int a, int b, int c, int m, int d, int e, int f) {
        return of(n, a, b, c).startsWith(of(m, d, e, f));
    }

    /** The compiler's concatenation of two Strings and a constant, null as "null". */
    static String concatenated(int n, int a, int b, int c, int m, int d, int e, int f) {
        return of(n, a, b, c) + "-" + of(m, d, e, f);
    }

    /** The compiler's concatenation of a String and a char. */
    static String withChar(int n, int a, int b, int c, int d) {
        return of(n, a, b, c) + (char) d;
    }

    /** A literal's code units: NUL and a supplementary character's pair, which the class file keeps. */
    static int literalUnit(int i) {
        return "A\u0000😀".charAt(i);
    }

    static boolean literalInterned() {
        return "ab" == "a" + "b";
    }

    /** A literal's isolated surrogates, which the class file keeps unit for unit, as it keeps a pair. */
    static int literalLoneSurrogate(int i) {
        return "\uDBFFa\uDC00\uD83D".charAt(i);
    }

    /** Two literals that differ only in an isolated surrogate are two Strings, of two contents. */
    static int literalsOfLoneSurrogates() {
        String high = "\uDBFF";
        String other = "\uDBFE";
        return (high == other ? 4 : 0) + (high.equals(other) ? 2 : 0) + (high == "\uDBFF" ? 1 : 0);
    }

    // java.util.List: List.of, List.copyOf, size, isEmpty, get, the iterator and the changes they refuse

    /** An element: a mutable application object. */
    static final class Item {
        int value;

        Item(int value) {
            this.value = value;
        }
    }

    /** n distinct items (0 to 10, List.of's fixed forms), item i of value i. */
    static List<Item> items(int n) {
        Item[] m = new Item[10];
        for (int i = 0; i < 10; i++) {
            m[i] = new Item(i);
        }
        switch (n) {
            case 0:
                return List.of();
            case 1:
                return List.of(m[0]);
            case 2:
                return List.of(m[0], m[1]);
            case 3:
                return List.of(m[0], m[1], m[2]);
            case 4:
                return List.of(m[0], m[1], m[2], m[3]);
            case 5:
                return List.of(m[0], m[1], m[2], m[3], m[4]);
            case 6:
                return List.of(m[0], m[1], m[2], m[3], m[4], m[5]);
            case 7:
                return List.of(m[0], m[1], m[2], m[3], m[4], m[5], m[6]);
            case 8:
                return List.of(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7]);
            case 9:
                return List.of(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
            default:
                return List.of(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9]);
        }
    }

    /** List.of over n elements of which the one at index at is null: a NullPointerException where it is one of them. */
    static int ofWithNull(int n, int at) {
        Item x = new Item(0);
        Item a = at == 0 ? null : x;
        Item b = at == 1 ? null : x;
        Item c = at == 2 ? null : x;
        List<Item> l = n == 1 ? List.of(a) : n == 2 ? List.of(a, b) : List.of(a, b, c);
        return l.size();
    }

    /** List.of keeps a duplicate and the identity of its elements: element 1 is element 0's object. */
    static boolean ofKeepsDuplicates(int v) {
        Item x = new Item(v);
        List<Item> l = List.of(x, x, new Item(v));
        return l.size() == 3 && l.get(0) == l.get(1) && l.get(1) != l.get(2);
    }

    /** An element is the object given, not a copy: a change through the list is seen through the object. */
    static int elementsAreTheObjects(int v) {
        Item x = new Item(0);
        List<Item> l = List.of(x);
        l.get(0).value = v;
        return x.value;
    }

    static boolean emptyIsShared() {
        return List.of() == List.of();
    }

    static boolean otherwiseFresh(int n) {
        Item x = new Item(0);
        return n == 1 ? List.of(x) != List.of(x) : List.of(x, x, x) != List.of(x, x, x);
    }

    static int size(int n) {
        return items(n).size();
    }

    static boolean isEmptyList(int n) {
        return items(n).isEmpty();
    }

    /** Element i's value: IndexOutOfBoundsException out of range for a list of one or two, ArrayIndexOutOfBoundsException otherwise. */
    static int get(int n, int i) {
        return items(n).get(i).value;
    }

    /** The values, in order, by an enhanced for, as a number in base 16. */
    static int iterated(int n) {
        int out = 0;
        for (Item it : items(n)) {
            out = out * 16 + it.value + 1;
        }
        return out;
    }

    /** next() k times: NoSuchElementException past the end. */
    static int nextPastTheEnd(int n, int k) {
        Iterator<Item> it = items(n).iterator();
        int last = -1;
        for (int i = 0; i < k; i++) {
            last = it.next().value;
        }
        return it.hasNext() ? last : -2 - last;
    }

    static boolean add(int n) {
        return items(n).add(new Item(0));
    }

    static int set(int n, int i) {
        return items(n).set(i, new Item(0)).value;
    }

    static int removeAt(int n, int i) {
        return items(n).remove(i).value;
    }

    static int clear(int n) {
        List<Item> l = items(n);
        l.clear();
        return l.size();
    }

    static int iteratorRemove(int n) {
        Iterator<Item> it = items(n).iterator();
        it.next();
        it.remove();
        return 0;
    }

    /** copyOf of a list of the family is the list itself; of null a NullPointerException. */
    static boolean copyOfIsTheList(int n) {
        List<Item> l = n < 0 ? null : items(n);
        return List.copyOf(l) == l;
    }
}
