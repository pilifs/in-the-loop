package basket;

import java.util.List;

/** Kernels over an immutable list of lines (List.of, List.copyOf), which rejects null elements. */
public final class Basket {
    private Basket() {
    }

    /** The total of the lines, in order: a line twice counts twice. */
    public static long total(List<Line> lines) {
        long total = 0;
        for (int i = 0; i < lines.size(); i++) {
            Line line = lines.get(i);
            total = total + line.unitCents * line.quantity;
        }
        return total;
    }

    /** The first line, the caller's own object; null for an empty list. */
    public static Line first(List<Line> lines) {
        if (lines.size() == 0) {
            return null;
        }
        return lines.get(0);
    }

    /** Clears the quantity of every line, then the total: an element twice, or two of one object, is cleared once. */
    public static long clearAll(List<Line> lines) {
        long cleared = 0;
        for (int i = 0; i < lines.size(); i++) {
            Line line = lines.get(i);
            cleared = cleared + line.quantity;
            line.quantity = 0;
        }
        return cleared;
    }
}
