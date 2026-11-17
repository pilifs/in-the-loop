package lc;

/** Reads the final static field its superclass declares: 7 once the superclass is initialized, 0 while it is. */
public class Derived extends Base {
    public static int limit() {
        return LIMIT;
    }
}
