package lc;

/** A final static field its initializer copies from a static a caller can write before the class is initialized. */
public final class Own {
    public static final int LIMIT = Settings.value;

    /** LIMIT: what Settings.value was when Own was initialized. */
    public static int limit() {
        return LIMIT;
    }
}
