import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import witness.OriginalWire;

public final class ReplayWire {
    public static void main(String[] args) throws Exception {
        OriginalWire.open(args[0], args[1], args[2]);
        for (Method m : WireClaims.class.getDeclaredMethods()) {
            if (m.getName().equals(args[3])) {
                Object[] inputs = Runner.arguments(m.getParameterTypes(), args[4]);
                try {
                    System.out.println(Boolean.TRUE.equals(m.invoke(null, inputs)) ? "held" : "refuted");
                } catch (InvocationTargetException e) {
                    Throwable t = e.getCause();
                    System.out.println("threw " + t.getClass().getName());
                    t.printStackTrace(System.err);
                }
                return;
            }
        }
        throw new IllegalArgumentException("unknown observation");
    }
}
