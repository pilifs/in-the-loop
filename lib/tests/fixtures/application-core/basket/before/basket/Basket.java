package basket;

import java.util.List;

/** Kernels over an immutable list of lines (List.of, List.copyOf), which rejects null elements. */
public final class Basket {
    private Basket() {
    }

    /** The total of the lines, in order: a line twice counts twice. */
    public static long total(List<Line> lines) {
        long total = 0;
        for (Line line : lines) {
            total += line.unitCents * line.quantity;
        }
        return total;
    }

    /** The first line, the caller's own object; null for an empty list. */
    public static Line first(List<Line> lines) {
        return lines.isEmpty() ? null : lines.get(0);
    }

    /** Clears the quantity of every line, then the total: an element twice, or two of one object, is cleared once. */
    public static long clearAll(List<Line> lines) {
        long cleared = 0;
        for (Line line : lines) {
            cleared += line.quantity;
            line.quantity = 0;
        }
        return cleared;
    }
}
