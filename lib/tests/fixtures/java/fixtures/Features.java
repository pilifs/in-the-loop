package fixtures;

import java.util.List;
import java.util.Optional;

/** Methods that exercise the interpreter's model of the JDK, with known contracts. */
public final class Features {

    public enum Tier {
        BASIC, PLUS, PRO;

        /** An instance method: the receiver is the domain. */
        public int discount() {
            return switch (this) {
                case BASIC -> 0;
                case PLUS -> 10;
                case PRO -> 25;
            };
        }
    }

    public record Order(Tier tier, boolean rush) {}

    public sealed interface Shape permits Circle, Square {}

    public record Circle(boolean big) implements Shape {}

    public record Square(Tier tier) implements Shape {}

    public record Quote(String label, long cents, List<Tier> tiers) {}

    private static final int[] COUNTS = new int[3];

    private Features() {}

    /** String concatenation, records, List.of, exact arithmetic, a ternary. */
    public static Quote quote(Order order) {
        long base = 1000L * (order.tier().ordinal() + 1);
        long cents = Math.multiplyExact(base, order.rush() ? 2 : 1) - base * order.tier().discount() / 100;
        return new Quote(order.tier().name().toLowerCase() + (order.rush() ? "-rush" : ""), cents, List.of(order.tier()));
    }

    /** A pattern switch over a sealed type, an enum switch (javac's $SwitchMap), a loop and a StringBuilder. */
    public static String describe(Shape shape) {
        return switch (shape) {
            case Circle c -> c.big() ? "big circle" : "circle";
            case Square sq -> switch (sq.tier()) {
                case BASIC -> "basic square";
                case PLUS, PRO -> repeat("square", sq.tier().ordinal() + 1);
            };
        };
    }

    private static String repeat(String s, int n) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < n; i++) {
            if (i > 0) {
                b.append('+');
            }
            b.append(s);
        }
        return b.toString();
    }

    /** A capturing lambda on a primitive functional interface. */
    public static int lambdas(Tier t) {
        java.util.function.IntUnaryOperator f = x -> x * 2 + t.ordinal();
        return f.applyAsInt(21);
    }

    /** Optional with a lambda and a method reference. */
    public static Optional<String> maybe(Tier t) {
        return Optional.of(t).filter(x -> x != Tier.BASIC).map(Tier::name);
    }

    /** An exception with a message built at runtime. */
    public static int throwsWithMessage(Tier t) {
        if (t == Tier.PRO) {
            throw new IllegalStateException("pro: " + t.ordinal());
        }
        return t.ordinal();
    }

    /** Writes into a static final array: invisible to the static purity analysis, caught by the effect monitor. */
    public static int impure(Tier t) {
        COUNTS[t.ordinal()]++;
        return COUNTS[t.ordinal()];
    }

    /** `values()` (an array clone) and an enhanced for over an array. */
    public static int sum(Tier t) {
        int s = 0;
        for (Tier x : Tier.values()) {
            s += x.ordinal();
        }
        return s + t.ordinal();
    }

    /** Record equals and hashCode, through ObjectMethods; a null argument throws. */
    public static boolean same(Order a, Order b) {
        return a.equals(b) && a.hashCode() == b.hashCode();
    }

    /** Integer division by zero, caught and reported as the JVM reports it. */
    public static long ratio(Tier a, Tier b) {
        return 100L * a.ordinal() / b.ordinal();
    }

    /** Unbounded recursion on one input: the step budget refuses it rather than hanging. */
    public static int loops(Tier t) {
        return t == Tier.PRO ? loops(t) : t.ordinal();
    }
}
