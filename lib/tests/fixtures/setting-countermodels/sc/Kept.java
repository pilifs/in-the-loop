package sc;

/**
 * Reads a system property as the value Properties.putIfAbsent returns: where the property is set, the map is left as
 * it was, and the value is the property's.
 */
public class Kept {
    public static final String VALUE;

    static {
        Object old = System.getProperties().putIfAbsent("sc.value", "absent");
        VALUE = old == null ? "absent" : (String) old;
    }
}
