package lc;

/** The same cycle with no inheritance: Reader is no subclass of Holder, so initializing it leaves Holder alone. */
public final class Holder {
    public static final int SEEN = Reader.limit();
    public static final int LIMIT = Integer.parseInt("7");
}
