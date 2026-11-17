package lc;

/** Initializes a field by a call that reads the class's own final static field before it is written: 0 there. */
public class Base {
    public static final int SEEN = Derived.limit();
    public static final int LIMIT = Integer.parseInt("7");
}
