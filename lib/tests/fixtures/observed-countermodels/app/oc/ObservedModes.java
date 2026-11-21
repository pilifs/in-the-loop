package oc;

public enum ObservedModes {
    FIRST("first"), SECOND(System.getProperty("oc.mode", "second"));

    static final ObservedModes ALIAS = SECOND;
    private final String name;
    private final int ordinal;

    ObservedModes(String label) {
        name = label;
        ordinal = 17;
    }

    public static boolean matches(boolean second) {
        ObservedModes value = values()[second ? 1 : 0];
        return value == (second ? ALIAS : FIRST)
                && value.name() == (second ? "SECOND" : "FIRST")
                && value.ordinal() == (second ? 1 : 0)
                && value.name.equals(second ? "second" : "first")
                && value.ordinal == 17;
    }

    public static boolean stableHash() {
        return ALIAS.hashCode() == SECOND.hashCode();
    }

    static final class Borrower {
        static final ObservedModes COPIED = ALIAS;
        public static boolean matches() { return COPIED == ObservedModes.SECOND; }
    }

    public static void main(String[] args) {
        System.out.println(matches(false) + " " + matches(true) + " " + stableHash() + " " + Borrower.matches());
    }
}
