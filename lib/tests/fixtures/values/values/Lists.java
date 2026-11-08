package values;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.NoSuchElementException;

/**
 * Harness-shaped checks of the own checker's immutable lists (lib/tests/values.rs): each static method throws an
 * AssertionError where its claim fails, as a generated harness does, and the checker is run on it directly. A
 * violation's witness is replayed on the JVM (ValuesRunner) and in the interpreter, and must throw that AssertionError.
 *
 * The kernels are the application-core basket's (lib/tests/fixtures/application-core/basket): before walks the list
 * with an enhanced for, after by index, and each defect is the basket's. Every list is made as a harness makes one,
 * by List.of over lines made by their constructor: n of them (0 to 3), element i the line its choice names, so that
 * any two may be one object. Each version gets a world of its own, made from the same inputs.
 */
public final class Lists {
    private Lists() {
    }

    /** A line of a basket: a mutable quantity of a unit price. */
    static final class Line {
        final long unitCents;
        int quantity;

        Line(long unitCents, int quantity) {
            if (quantity < 0) {
                throw new IllegalArgumentException("negative quantity");
            }
            this.unitCents = unitCents;
            this.quantity = quantity;
        }
    }

    /** Whether the inputs are in the domain: 0 to 3 elements, each choice naming a line made so far, no negative quantity. */
    static boolean admitted(int n, int c1, int c2, int q0, int q1, int q2) {
        return n >= 0 && n <= 3 && c1 >= 0 && c1 <= 1 && c2 >= 0 && c2 <= 2 && q0 >= 0 && q1 >= 0 && q2 >= 0;
    }

    /** The list of a world: n elements, element 0 the first line, element 1 the first or second, element 2 any of three. */
    static List<Line> list(int n, int c1, int c2, int u0, int q0, int u1, int q1, int u2, int q2) {
        Line a = new Line(u0, q0);
        Line b = new Line(u1, q1);
        Line c = new Line(u2, q2);
        Line e1 = c1 == 0 ? a : b;
        Line e2 = c2 == 0 ? a : c2 == 1 ? b : c;
        switch (n) {
            case 0:
                return List.of();
            case 1:
                return List.of(a);
            case 2:
                return List.of(a, e1);
            default:
                return List.of(a, e1, e2);
        }
    }

    static long totalBefore(List<Line> lines) {
        long total = 0;
        for (Line line : lines) {
            total += line.unitCents * line.quantity;
        }
        return total;
    }

    static long totalAfter(List<Line> lines) {
        long total = 0;
        for (int i = 0; i < lines.size(); i++) {
            Line line = lines.get(i);
            total = total + line.unitCents * line.quantity;
        }
        return total;
    }

    /** The basket's defect duplicate-skipped: a line given twice in a row counts once. */
    static long totalDuplicateSkipped(List<Line> lines) {
        long total = 0;
        Line previous = null;
        for (int i = 0; i < lines.size(); i++) {
            Line line = lines.get(i);
            if (line != previous) {
                total = total + line.unitCents * line.quantity;
            }
            previous = line;
        }
        return total;
    }

    static Line firstBefore(List<Line> lines) {
        return lines.isEmpty() ? null : lines.get(0);
    }

    static Line firstAfter(List<Line> lines) {
        if (lines.size() == 0) {
            return null;
        }
        return lines.get(0);
    }

    /** The basket's defect last-not-first: the last line, a reordering. */
    static Line firstIsLast(List<Line> lines) {
        if (lines.size() == 0) {
            return null;
        }
        return lines.get(lines.size() - 1);
    }

    /** The basket's defect copied-first: a copy of the first line, equal in every field but another object. */
    static Line firstCopied(List<Line> lines) {
        if (lines.size() == 0) {
            return null;
        }
        Line line = lines.get(0);
        return new Line(line.unitCents, line.quantity);
    }

    static long clearBefore(List<Line> lines) {
        long cleared = 0;
        for (Line line : lines) {
            cleared += line.quantity;
            line.quantity = 0;
        }
        return cleared;
    }

    static long clearAfter(List<Line> lines) {
        long cleared = 0;
        for (int i = 0; i < lines.size(); i++) {
            Line line = lines.get(i);
            cleared = cleared + line.quantity;
            line.quantity = 0;
        }
        return cleared;
    }

    /** The basket's defect alias-blind: reads every line before clearing any, so one object given twice counts twice. */
    static long clearAliasBlind(List<Line> lines) {
        long cleared = 0;
        for (int i = 0; i < lines.size(); i++) {
            cleared = cleared + lines.get(i).quantity;
        }
        for (int i = 0; i < lines.size(); i++) {
            lines.get(i).quantity = 0;
        }
        return cleared;
    }

    /** Where the result is in its world's list, by identity: its first index, -1 for none, -2 for null. */
    static int position(List<Line> lines, Line result) {
        if (result == null) {
            return -2;
        }
        for (int i = 0; i < lines.size(); i++) {
            if (lines.get(i) == result) {
                return i;
            }
        }
        return -1;
    }

    /** total's rewrite by index: the same total on every list, in its world. */
    public static void totalRewritten(int n, int c1, int c2, int u0, int q0, int u1, int q1, int u2, int q2) {
        if (!admitted(n, c1, c2, q0, q1, q2)) {
            return;
        }
        if (totalBefore(list(n, c1, c2, u0, q0, u1, q1, u2, q2)) != totalAfter(list(n, c1, c2, u0, q0, u1, q1, u2, q2))) {
            throw new AssertionError();
        }
    }

    /** Refuted by a line given twice in a row: a duplicate element counts. */
    public static void totalSkippingDuplicates(int n, int c1, int c2, int u0, int q0, int u1, int q1, int u2, int q2) {
        if (!admitted(n, c1, c2, q0, q1, q2)) {
            return;
        }
        if (totalBefore(list(n, c1, c2, u0, q0, u1, q1, u2, q2)) != totalDuplicateSkipped(list(n, c1, c2, u0, q0, u1, q1, u2, q2))) {
            throw new AssertionError();
        }
    }

    /** first's rewrite: the same line, by its place in the list (null for an empty one). */
    public static void firstRewritten(int n, int c1, int c2, int u0, int q0, int u1, int q1, int u2, int q2) {
        if (!admitted(n, c1, c2, q0, q1, q2)) {
            return;
        }
        List<Line> before = list(n, c1, c2, u0, q0, u1, q1, u2, q2);
        List<Line> after = list(n, c1, c2, u0, q0, u1, q1, u2, q2);
        if (position(before, firstBefore(before)) != position(after, firstAfter(after))) {
            throw new AssertionError();
        }
    }

    /** Refuted by two different lines: the order of the elements is kept. */
    public static void firstReordered(int n, int c1, int c2, int u0, int q0, int u1, int q1, int u2, int q2) {
        if (!admitted(n, c1, c2, q0, q1, q2)) {
            return;
        }
        List<Line> before = list(n, c1, c2, u0, q0, u1, q1, u2, q2);
        List<Line> after = list(n, c1, c2, u0, q0, u1, q1, u2, q2);
        if (position(before, firstBefore(before)) != position(after, firstIsLast(after))) {
            throw new AssertionError();
        }
    }

    /** Refuted by any line: a copy is not the element, however equal its fields. */
    public static void firstByCopy(int n, int c1, int c2, int u0, int q0, int u1, int q1, int u2, int q2) {
        if (!admitted(n, c1, c2, q0, q1, q2)) {
            return;
        }
        List<Line> before = list(n, c1, c2, u0, q0, u1, q1, u2, q2);
        List<Line> after = list(n, c1, c2, u0, q0, u1, q1, u2, q2);
        if (position(before, firstBefore(before)) != position(after, firstCopied(after))) {
            throw new AssertionError();
        }
    }

    /** clearAll's rewrite: the same total cleared, an element given twice cleared once. */
    public static void clearRewritten(int n, int c1, int c2, int u0, int q0, int u1, int q1, int u2, int q2) {
        if (!admitted(n, c1, c2, q0, q1, q2)) {
            return;
        }
        if (clearBefore(list(n, c1, c2, u0, q0, u1, q1, u2, q2)) != clearAfter(list(n, c1, c2, u0, q0, u1, q1, u2, q2))) {
            throw new AssertionError();
        }
    }

    /** Refuted only by one object given twice with a quantity: an alias between elements is kept. */
    public static void clearBlindToAliases(int n, int c1, int c2, int u0, int q0, int u1, int q1, int u2, int q2) {
        if (!admitted(n, c1, c2, q0, q1, q2)) {
            return;
        }
        if (clearBefore(list(n, c1, c2, u0, q0, u1, q1, u2, q2)) != clearAliasBlind(list(n, c1, c2, u0, q0, u1, q1, u2, q2))) {
            throw new AssertionError();
        }
    }

    /** A wrong claim, that clearing two elements clears two lines: refuted by one object given twice. */
    public static void elementsAreDistinct(int n, int c1, int c2, int u0, int q0, int u1, int q1, int u2, int q2) {
        if (!admitted(n, c1, c2, q0, q1, q2)) {
            return;
        }
        List<Line> lines = list(n, c1, c2, u0, q0, u1, q1, u2, q2);
        if (n >= 2 && lines.get(0) == lines.get(1)) {
            throw new AssertionError();
        }
    }

    /** size and isEmpty agree with the number of elements made, and the iterator gives each in order, then ends. */
    public static void sizeAndIteration(int n, int c1, int c2, int u0, int q0, int u1, int q1, int u2, int q2) {
        if (!admitted(n, c1, c2, q0, q1, q2)) {
            return;
        }
        List<Line> lines = list(n, c1, c2, u0, q0, u1, q1, u2, q2);
        if (lines.size() != n || lines.isEmpty() != (n == 0)) {
            throw new AssertionError();
        }
        Iterator<Line> it = lines.iterator();
        for (int i = 0; i < n; i++) {
            if (!it.hasNext() || it.next() != lines.get(i)) {
                throw new AssertionError();
            }
        }
        if (it.hasNext()) {
            throw new AssertionError();
        }
        try {
            it.next();
            throw new AssertionError();
        } catch (NoSuchElementException expected) {
            // past the end
        }
    }

    /** get out of range throws as the JDK's classes do: IndexOutOfBoundsException from a list of one or two, an
     * ArrayIndexOutOfBoundsException (its subclass) from any other, which indexes an array of its own. */
    public static void getOutOfRange(int n, int c1, int c2, int index) {
        if (!admitted(n, c1, c2, 0, 0, 0) || (index >= 0 && index < n)) {
            return;
        }
        List<Line> lines = list(n, c1, c2, 1, 1, 2, 2, 3, 3);
        try {
            lines.get(index);
        } catch (ArrayIndexOutOfBoundsException e) {
            if (n == 1 || n == 2) {
                throw new AssertionError();
            }
            return;
        } catch (IndexOutOfBoundsException e) {
            if (n == 0 || n == 3) {
                throw new AssertionError();
            }
            return;
        }
        throw new AssertionError();
    }

    /** A wrong claim, that every list's get throws the same class out of range: refuted by both kinds. */
    public static void getThrowsOneClass(int n, int c1, int c2) {
        if (!admitted(n, c1, c2, 0, 0, 0)) {
            return;
        }
        try {
            list(n, c1, c2, 1, 1, 2, 2, 3, 3).get(n);
        } catch (ArrayIndexOutOfBoundsException e) {
            return;
        } catch (IndexOutOfBoundsException e) {
            throw new AssertionError();
        }
    }

    /** List.of refuses a null element, at any place: NullPointerException. */
    public static void ofRejectsNull(int n, int at) {
        if (n < 1 || n > 3 || at < 0 || at >= n) {
            return;
        }
        Line a = new Line(1, 1);
        Line e0 = at == 0 ? null : a;
        Line e1 = at == 1 ? null : a;
        Line e2 = at == 2 ? null : a;
        try {
            if (n == 1) {
                List.of(e0);
            } else if (n == 2) {
                List.of(e0, e1);
            } else {
                List.of(e0, e1, e2);
            }
        } catch (NullPointerException expected) {
            return;
        }
        throw new AssertionError();
    }

    /** Every change is refused: UnsupportedOperationException, the list unchanged. */
    public static void changesAreRefused(int n, int c1, int c2) {
        if (!admitted(n, c1, c2, 0, 0, 0)) {
            return;
        }
        List<Line> lines = list(n, c1, c2, 1, 1, 2, 2, 3, 3);
        try {
            lines.add(new Line(4, 4));
            throw new AssertionError();
        } catch (UnsupportedOperationException expected) {
            // refused
        }
        try {
            lines.set(0, new Line(4, 4));
            throw new AssertionError();
        } catch (UnsupportedOperationException expected) {
            // refused, before any index check
        }
        if (lines.size() != n) {
            throw new AssertionError();
        }
    }

    /** List.copyOf of one of these lists is the list itself; the elements are not copied either. */
    public static void copyOfIsTheList(int n, int c1, int c2) {
        if (!admitted(n, c1, c2, 0, 0, 0)) {
            return;
        }
        List<Line> lines = list(n, c1, c2, 1, 1, 2, 2, 3, 3);
        if (List.copyOf(lines) != lines) {
            throw new AssertionError();
        }
    }

    /** The empty list is one object, whichever way it is made: List.of() twice. */
    public static void oneEmptyList(int n) {
        if ((Object) List.of() != List.<Line>of()) {
            throw new AssertionError();
        }
    }

    /** List.copyOf of a list of another implementation: the checker doesn't model ArrayList, and names it. */
    public static void copyOfAnotherImplementation(int n) {
        ArrayList<Line> source = new ArrayList<>();
        if (n > 0) {
            source.add(new Line(1, 1));
        }
        if (List.copyOf(source).size() != (n > 0 ? 1 : 0)) {
            throw new AssertionError();
        }
    }
}
