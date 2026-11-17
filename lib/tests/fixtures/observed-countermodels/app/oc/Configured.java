package oc;

/** An initializer whose result is a system property's, or "absent". */
public class Configured {
    public static final String VALUE;

    static {
        VALUE = System.getProperty("oc.value", "absent");
    }
}
