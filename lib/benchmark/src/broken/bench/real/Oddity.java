package bench.real;

/**
 * Joshua Bloch and Neal Gafter, Java Puzzlers (2005), Puzzle 1, "Oddity", before the fix: {@code i % 2 == 1} is false for
 * every negative odd {@code i}, since Java's remainder takes the sign of the dividend. The book's fix compares the
 * remainder with zero.
 */
public final class Oddity {
    private Oddity() {
    }

    public static boolean isOdd(int i) {
        return i % 2 == 1;
    }
}
