import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import org.jupiter.common.util.Reflects;

public final class UpgradeProbe {
    public interface Service {
        String method(Integer i, String value);
        String method(Integer i, CharSequence value);
        String method(int i, String value);
        String method(int i, CharSequence value);
        String method(long i, CharSequence value);
    }
    public static final class Impl implements Service {
        public String method(Integer i, String v) { return "Integer/String"; }
        public String method(Integer i, CharSequence v) { return "Integer/CharSequence"; }
        public String method(int i, String v) { return "int/String"; }
        public String method(int i, CharSequence v) { return "int/CharSequence"; }
        public String method(long i, CharSequence v) { return "long/CharSequence"; }
    }
    public static String observe(String[] args) {
        Object text = args[0].equals("builder") ? new StringBuilder("ss") : "ss";
        Object[] values = {Integer.valueOf(1), text};
        List<Class<?>[]> candidates = new ArrayList<>();
        for (Method m : Service.class.getMethods()) if (m.getName().equals("method")) candidates.add(m.getParameterTypes());
        Class<?>[] selected = Reflects.findMatchingParameterTypes(candidates, values);
        return (String) Reflects.fastInvoke(new Impl(), "method", selected, values);
    }
}
