package ob;

/** Reads a system property through the Properties map rather than getProperty. */
public class Bypassed {
    public static final String VALUE;

    static {
        Object v = System.getProperties().get("ob.value");
        VALUE = v == null ? "absent" : (String) v;
    }
}
