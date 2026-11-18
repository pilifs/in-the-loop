package lc;

/** A final static field its initializer lower-cases under the default locale a caller can set first. */
public final class Lowered {
    public static final String I = "I".toLowerCase();

    /** I's one code unit: 'i' (105), or the dotless i (305) where the default locale was Turkish at initialization. */
    public static int lowered() {
        return I.charAt(0);
    }
}
