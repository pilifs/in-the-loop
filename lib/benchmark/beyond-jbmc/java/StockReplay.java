import java.lang.reflect.Method;

/** The entry point returns 2 outside its domain, 1 or 0 on return, and -2 or -1 on a throw. */
public final class StockReplay {
    public static void main(String[] args) throws Exception {
        for (Method m : Class.forName(args[0], false, StockReplay.class.getClassLoader()).getDeclaredMethods()) {
            if (m.getName().equals("observe")) {
                Object[] values = Runner.arguments(m.getParameterTypes(), args[1]);
                System.out.println("observation=" + m.invoke(null, values));
                return;
            }
        }
        throw new IllegalArgumentException("no observation entry");
    }
}
