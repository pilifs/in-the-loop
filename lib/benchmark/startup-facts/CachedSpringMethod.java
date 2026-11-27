import java.lang.reflect.Method;
import java.util.Arrays;

/** Labelled variant of the registered override history. Keep the exact non-bridge declaration. */
public class CachedSpringMethod {
    static final Method METHOD = Arrays.stream(PublicCaller.Text.class.getDeclaredMethods())
            .filter(m -> m.getName().equals("get") && !m.isBridge()).findFirst().orElseThrow();
    public static int count() { return METHOD.getParameterCount(); }
}
