package claims;

/** Constructor branches are reached with the actual arguments from each class initializer. */
public class ValueConstants {
    static class Value {
        final int number;
        Value(int n) {
            if (n < 0) throw new IllegalArgumentException();
            number = n == 0 ? (int) Double.parseDouble("9") : n == 1 ? (int) Double.parseDouble("0x1.2p3") : n;
        }
    }

    static class Good {
        static final Value FIRST = new Value(3);
        static final Value SECOND = new Value(5);
    }

    static class Decimal {
        static final Value VALUE = new Value(0);
    }

    static class Hexadecimal {
        static final Value VALUE = new Value(1);
    }

    static class Failed {
        static final Value VALUE = new Value(-1);
    }

    public static boolean kept() {
        return Good.FIRST.number == 3 && Good.SECOND.number == 5 && Good.FIRST != Good.SECOND;
    }

    public static boolean parses() {
        return Decimal.VALUE.number == 9;
    }

    public static boolean parsesHex() {
        return Hexadecimal.VALUE.number == 9;
    }

    public static boolean failureState() {
        try {
            return Failed.VALUE == null;
        } catch (ExceptionInInitializerError expected) {
            try {
                return Failed.VALUE == null;
            } catch (NoClassDefFoundError erroneous) {
                return true;
            }
        }
    }

    public static void main(String[] args) {
        if (!kept() || !parses() || !parsesHex() || !failureState()) throw new AssertionError();
    }
}
