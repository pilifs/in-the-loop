package lc;

/** Reads another class's final static field: 7 once Holder is initialized, 0 while it is. */
public final class Reader {
    public static int limit() {
        return Holder.LIMIT;
    }
}
