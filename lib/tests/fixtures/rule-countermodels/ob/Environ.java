package ob;

/** An environment variable's length when the class was initialized, 6 ("absent") where it is not set. */
public class Environ {
    public static final String VALUE;

    static {
        String v = System.getenv("OB_VALUE");
        VALUE = v == null ? "absent" : v;
    }
}
