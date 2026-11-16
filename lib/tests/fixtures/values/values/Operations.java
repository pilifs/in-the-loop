package values;

import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.regex.Pattern;

/**
 * The boundary cases of every operation the values models implement (lib/tests/values.rs,
 * values::operations): each static method calls one operation on values made from its int arguments, and the test
 * runs it on the JVM, in the interpreter and in the own checker (through a generated method asserting the JVM's
 * outcome), which must all agree. Each operation's evidence record names the methods that sample it, and the
 * exceptions they were seen to throw.
 *
 * A String is made at run time by concatenating chars (never a literal with an isolated surrogate, which the class
 * reader decodes lossily), a list by List.of over items made by their constructor, and a map by HashMap's
 * constructors and put, its keys Strings made the same way.
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

    static boolean endsWith(int n, int a, int b, int c, int m, int d, int e, int f) {
        return of(n, a, b, c).endsWith(of(m, d, e, f));
    }

    static int indexOfChar(int n, int a, int b, int c, int ch) {
        return of(n, a, b, c).indexOf(ch);
    }

    static int indexOfCharFrom(int n, int a, int b, int c, int ch, int from) {
        return of(n, a, b, c).indexOf(ch, from);
    }

    static int indexOfString(int n, int a, int b, int c, int m, int d, int e, int f) {
        return of(n, a, b, c).indexOf(of(m, d, e, f));
    }

    static int indexOfStringFrom(int n, int a, int b, int c, int m, int d, int e, int from) {
        return of(n, a, b, c).indexOf(of(m, d, e, 0), from);
    }

    /**
     * What a method made of s, against the content expected: 0 for another content, 2 for s itself, 3 for the
     * literal "", 1 for any other String of that content.
     */
    static int made(String s, String part, String want) {
        if (!part.equals(want)) {
            return 0;
        }
        return part == s ? 2 : part == "" ? 3 : 1;
    }

    static int substringFrom(int n, int a, int b, int c, int from, int m, int d, int e, int f) {
        String s = of(n, a, b, c);
        return made(s, s.substring(from), of(m, d, e, f));
    }

    static int substring(int n, int a, int b, int c, int from, int to, int m, int d, int e, int f) {
        String s = of(n, a, b, c);
        return made(s, s.substring(from, to), of(m, d, e, f));
    }

    static int toLowerCase(int n, int a, int b, int c, int m, int d, int e, int f) {
        String s = of(n, a, b, c);
        return made(s, s.toLowerCase(), of(m, d, e, f));
    }

    /** The parts at one character, every one kept: how many for a negative i, else what the ith is. */
    static int split(int n, int a, int b, int c, int i, int m, int d, int e, int f) {
        String s = of(n, a, b, c);
        String[] parts = s.split("\\*", -1);
        return i < 0 ? parts.length : made(s, parts[i], of(m, d, e, f));
    }

    static int splitByNull(int n, int a, int b, int c) {
        return of(n, a, b, c).split(null, -1).length;
    }

    /** Whether every code unit, as the int the stream gives, is below the limit. */
    static boolean chars(int n, int a, int b, int c, int limit) {
        return of(n, a, b, c).chars().allMatch(u -> u >= 0 && u < limit);
    }

    /** The UTF-8 encoding: how many bytes for a negative i, else the ith. */
    static int getBytes(int n, int a, int b, int c, int i) {
        byte[] bytes = of(n, a, b, c).getBytes(StandardCharsets.UTF_8);
        return i < 0 ? bytes.length : bytes[i];
    }

    static int getBytesByNull(int n, int a, int b, int c) {
        return of(n, a, b, c).getBytes((Charset) null).length;
    }

    /** A constant regular expression of classes, a group of alternatives and counts, against the whole String. */
    static boolean matches(int n, int a, int b, int c) {
        return of(n, a, b, c).matches("[a-c]x{1,2}|(\\d|\\$)[^0-9]?");
    }

    static boolean matchesByNull(int n, int a, int b, int c) {
        return of(n, a, b, c).matches(null);
    }

    /** A String's toString is the String itself: 2. */
    static int toString(int n, int a, int b, int c) {
        String s = of(n, a, b, c);
        return made(s, s.toString(), s);
    }

    /** toString called through Object runs the String's, as the JVM dispatches it. */
    static int toStringAsObject(int n, int a, int b, int c) {
        String s = of(n, a, b, c);
        Object o = s;
        return made(s, o.toString(), s);
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

    static int hashCode(int n, int a, int b, int c) {
        return of(n, a, b, c).hashCode();
    }

    /** Of twice the code units, where the sum passes an int. */
    static int hashCodeOfConcatenation(int n, int a, int b, int c) {
        return (of(n, a, b, c) + of(n, a, b, c)).hashCode();
    }

    // java.lang.String, called as the Object or the CharSequence it is: the bytecode names that class, and the JVM
    // runs the String's method.

    static int hashCodeThroughObject(int n, int a, int b, int c) {
        Object o = of(n, a, b, c);
        return o.hashCode();
    }

    static boolean equalsThroughObject(int n, int a, int b, int c, int m, int d, int e, int f) {
        Object o = of(n, a, b, c);
        return o.equals(of(m, d, e, f));
    }

    static int lengthThroughCharSequence(int n, int a, int b, int c) {
        CharSequence s = of(n, a, b, c);
        return s.length();
    }

    static int charAtThroughCharSequence(int n, int a, int b, int c, int i) {
        CharSequence s = of(n, a, b, c);
        return s.charAt(i);
    }

    static boolean isEmptyThroughCharSequence(int n, int a, int b, int c) {
        CharSequence s = of(n, a, b, c);
        return s.isEmpty();
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

    // java.util.HashMap: HashMap(), HashMap(int), put, get, containsKey, size and isEmpty, over String keys

    /** The key of index i: a fresh String of one letter, "a" for 0. */
    static String key(int i) {
        return of(1, 'a' + i, 0, 0);
    }

    /** A map of the first n keys, key i to an item of value i, called as the Map it is. */
    static Map<String, Item> map(int n) {
        Map<String, Item> m = new HashMap<>();
        for (int i = 0; i < n; i++) {
            m.put(key(i), new Item(i));
        }
        return m;
    }

    static int mapNew() {
        return new HashMap<String, Item>().size();
    }

    /** An IllegalArgumentException for a negative capacity. */
    static int mapOfCapacity(int capacity) {
        return new HashMap<String, Item>(capacity).size();
    }

    /** A new key's put returns null and adds it: 1, and ten times the size after. */
    static int mapPut(int n) {
        Map<String, Item> m = map(n);
        return (m.put(key(n), new Item(n)) == null ? 1 : 0) + 10 * m.size();
    }

    /** A put of key k over the first n: the value it returns (-1 for none), the one held after, and the size. */
    static int mapPutReplaces(int n, int k) {
        Map<String, Item> m = map(n);
        Item old = m.put(key(k), new Item(7));
        return (old == null ? -1 : old.value) * 100 + m.get(key(k)).value * 10 + m.size();
    }

    /** null is a key like any other: added, replaced, found and counted. */
    static int mapPutNullKey() {
        Map<String, Item> m = map(2);
        int first = m.put(null, new Item(7)) == null ? 1 : 0;
        int second = m.put(null, new Item(8)).value;
        return first * 1000 + second * 100 + m.get(null).value * 10 + m.size();
    }

    /** The value of key k among the first n, -1 where it has none. */
    static int mapGet(int n, int k) {
        Item item = map(n).get(key(k));
        return item == null ? -1 : item.value;
    }

    /** A key is found by content: by another String of the same code units, the empty one and null included. */
    static int mapGetEqualKey(int n, int a, int b, int c) {
        Map<String, Item> m = map(2);
        m.put(of(n, a, b, c), new Item(5));
        return m.get(of(n, a, b, c)).value * 10 + m.size();
    }

    static boolean mapGetNullKey(int n) {
        return map(n).get(null) == null;
    }

    /** A key held with a null value: get returns null, as for a key not held. */
    static boolean mapGetNullValue() {
        Map<String, Item> m = new HashMap<>();
        return m.put("a", null) == null && m.get("a") == null && m.size() == 1;
    }

    /** "Aa" and "BB" have one hash code and are two keys, called on the HashMap itself. */
    static int mapGetCollidingKeys() {
        HashMap<String, Item> m = new HashMap<>(4);
        m.put(of(2, 'A', 'a', 0), new Item(1));
        m.put(of(2, 'B', 'B', 0), new Item(2));
        return m.get(of(2, 'A', 'a', 0)).value * 100 + m.get(of(2, 'B', 'B', 0)).value * 10 + m.size();
    }

    static boolean mapContainsKey(int n, int k) {
        return map(n).containsKey(key(k));
    }

    static boolean mapContainsNullValued() {
        Map<String, Item> m = new HashMap<>();
        m.put("a", null);
        return m.containsKey("a") && !m.containsKey("b") && !m.containsKey(null);
    }

    /** The first n keys, the first put again: counted once. */
    static int mapSize(int n) {
        Map<String, Item> m = map(n);
        if (n > 0) {
            m.put(key(0), new Item(9));
        }
        return m.size();
    }

    static boolean mapIsEmpty(int n) {
        return map(n).isEmpty();
    }

    // The JDK's static calls over references: Objects.requireNonNull and Pattern.compile of a plain constant

    /** The reference itself, or a NullPointerException for null. */
    static int requireNonNull(int n, int a, int b, int c) {
        String s = of(n, a, b, c);
        return Objects.requireNonNull(s) == s ? s.length() : -2;
    }

    static int requireNonNullWithMessage(int n, int a, int b, int c) {
        String s = of(n, a, b, c);
        return Objects.requireNonNull(s, "a String") == s ? s.length() : -2;
    }

    /** A constant regular expression of the plain form compiles; null is a NullPointerException. */
    static boolean patternCompile(int which) {
        String regex;
        switch (which) {
            case 0:
                regex = "//+";
                break;
            case 1:
                regex = "^/a?b*$";
                break;
            case 2:
                regex = "";
                break;
            default:
                regex = null;
        }
        return Pattern.compile(regex) != null;
    }

    static boolean patternsAreFresh() {
        return Pattern.compile("/$") != Pattern.compile("/$");
    }

    /** A constant with a class and a count compiles to a Pattern that says whether it matches all of a String. */
    static boolean patternMatches(int n, int a, int b, int c) {
        return Pattern.compile("\\A[./A-Za-z0-9]{2,3}").matcher(of(n, a, b, c)).matches();
    }
}
