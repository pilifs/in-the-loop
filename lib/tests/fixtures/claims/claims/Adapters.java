package claims;

import java.util.function.Function;

/**
 * An initializer in the shape of spring-jcl's LogAdapter: it asks the class path for a library, and keeps a method
 * reference for the one it finds. The reference it does not keep names a method the checker has no model of, which
 * is never called.
 */
final class Adapters {
    static final Function<String, String> MAKE;

    static {
        MAKE = present("no.such.Library") ? Adapters::reversed : Adapters::plain;
    }

    private Adapters() {}

    static boolean present(String name) {
        try {
            Class.forName(name, false, Adapters.class.getClassLoader());
            return true;
        } catch (Throwable e) {
            return false;
        }
    }

    static String plain(String s) {
        return s;
    }

    static String reversed(String s) {
        return new StringBuilder(s).reverse().toString();
    }
}
