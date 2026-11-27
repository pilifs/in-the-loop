import java.lang.reflect.Method;

/** A labelled premain control. The two launches have the same original static value. */
public class FirstUseControl {
    public static class Early {
        static final Method CACHED;
        static {
            try { CACHED = String.class.getMethod("trim"); }
            catch (NoSuchMethodException e) { throw new ExceptionInInitializerError(e); }
        }
        public static int arity() { return CACHED.getParameterCount(); }
    }

    public static void premain(String name) throws ClassNotFoundException {
        // The debugger controller and javac do not carry the subject's classpath.
        ClassLoader app = ClassLoader.getSystemClassLoader();
        if (app.getResource(name.replace('.', '/') + ".class") != null) Class.forName(name, true, app);
    }

    public static void main(String[] args) {
        System.out.println(Early.CACHED.toGenericString());
        System.out.println(Early.arity());
    }
}
