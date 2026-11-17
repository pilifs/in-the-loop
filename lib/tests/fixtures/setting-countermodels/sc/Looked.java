package sc;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;

/** Reads an environment variable through a method handle looked up by name: no constant of the class names System.getenv. */
public class Looked {
    public static final String VALUE;

    static {
        String v;
        try {
            v = (String) MethodHandles.publicLookup().findStatic(System.class, "getenv", MethodType.methodType(String.class, String.class)).invoke("SC_VALUE");
        }
        catch (Throwable t) {
            v = null;
        }
        VALUE = v == null ? "absent" : v;
    }
}
