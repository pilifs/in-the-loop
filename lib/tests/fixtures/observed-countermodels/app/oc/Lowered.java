package oc;

/** An initializer whose result is the default locale's: "I" lowered is "i" in English and dotless in Turkish. */
public class Lowered {
    public static final String I;

    static {
        I = "I".toLowerCase();
    }
}
