package javax.claims;

import java.util.IdentityHashMap;
import java.util.Map;

/**
 * A class of a JDK package that is no class of the JDK, as the servlet API's are: the own checker takes such a
 * class to be initialized already, as it takes the JDK's, unless a check has the observed state of its initializer
 * ({@code claims.M.served}).
 */
public class Library {
    static final Map<Object, Object> BUNDLE = new IdentityHashMap<>();
    public static final int MARK = Integer.parseInt("7");
}
