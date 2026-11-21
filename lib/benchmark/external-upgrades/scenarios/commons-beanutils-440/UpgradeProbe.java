import org.apache.commons.beanutils2.MethodUtils;
import java.lang.reflect.Method;

public final class UpgradeProbe {
    public static final class Choices {
        public void pick(Number value) { }
        public void pick(Integer value) { }
        public void pick(String value) { }
    }
    public static String observe(String[] args) throws Exception {
        Class<?> input = Class.forName("java.lang." + args[0]);
        Method selected = MethodUtils.getMatchingAccessibleMethod(Choices.class, "pick", new Class<?>[] {input});
        return selected == null ? null : selected.getParameterTypes()[0].getName();
    }
}
