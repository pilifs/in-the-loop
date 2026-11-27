package oc;

import java.lang.reflect.Method;
import java.util.Locale;

/** Two reflection copies of one declaration and an alias to the first. */
public class MemberStartup {
    static final Method FIRST, ALIAS, COPY;
    static {
        try {
            FIRST = Locale.class.getMethod("getUnicodeLocaleType", String.class);
            ALIAS = FIRST;
            COPY = Locale.class.getMethod("getUnicodeLocaleType", String.class);
        } catch (ReflectiveOperationException e) { throw new ExceptionInInitializerError(e); }
    }
    public static int arity() { return FIRST.getParameterCount(); }
    public static boolean aliases() { return FIRST == ALIAS && FIRST != COPY; }
    public static boolean invoked() throws ReflectiveOperationException { return FIRST.invoke(Locale.ROOT, "ca") == null; }

    public static class Opened {
        static final Method METHOD;
        static {
            try {
                METHOD = Locale.class.getMethod("getUnicodeLocaleType", String.class);
                METHOD.setAccessible(true);
            } catch (ReflectiveOperationException e) { throw new ExceptionInInitializerError(e); }
        }
        public static int count() { return METHOD.getParameterCount(); }
    }

    public static class Missing {
        static final Method METHOD;
        static {
            Method member;
            try { member = Locale.class.getMethod("absentStartupMethod", String.class); }
            catch (NoSuchMethodException absent) { member = null; }
            METHOD = member;
        }
        public static boolean absent() { return METHOD == null; }
    }
}
