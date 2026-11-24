import java.lang.reflect.Method;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.lang.reflect.TypeVariable;
import java.lang.reflect.WildcardType;
import java.util.List;
import org.springframework.core.GenericTypeResolver;
import org.springframework.core.ResolvableType;
import org.springframework.core.convert.converter.Converter;

public final class SpringTypes {
    public interface Supplier<T> { List<List<T>> get(); }
    public interface Strings extends Supplier<String> {}
    public interface Integers extends Supplier<Integer> {}
    public static final class Convert implements Converter<Enum<?>,String> {
        @Override public String convert(Enum<?> source) { return source.name(); }
    }

    static Class<?> nested(Type ret, Class<?> ctx) {
        return ResolvableType.forType(GenericTypeResolver.resolveType(ret, ctx)).getGeneric(0).getGeneric(0).resolve();
    }

    public static boolean publicMethod() throws Exception {
        Method m = Supplier.class.getMethod("get");
        return m.getDeclaringClass() == Supplier.class && m.getParameterCount() == 0 && m.getReturnType() == List.class;
    }

    public static boolean genericReturn() throws Exception {
        Method m = Supplier.class.getMethod("get");
        ParameterizedType outer = (ParameterizedType)m.getGenericReturnType();
        ParameterizedType inner = (ParameterizedType)outer.getActualTypeArguments()[0];
        TypeVariable<?> variable = (TypeVariable<?>)inner.getActualTypeArguments()[0];
        return outer.getRawType() == List.class && inner.getRawType() == List.class
                && variable.getName().equals("T") && variable.getBounds()[0] == Object.class
                && variable.equals(Supplier.class.getTypeParameters()[0]);
    }

    public static boolean resolved() throws Exception {
        Type ret = Supplier.class.getMethod("get").getGenericReturnType();
        Class<?> a = nested(ret, Strings.class), b = nested(ret, Integers.class), c = nested(ret, Strings.class);
        return a == String.class && b == Integer.class && c == String.class;
    }

    public static boolean unresolved() throws Exception {
        Type ret = Supplier.class.getMethod("get").getGenericReturnType();
        Class<?> a = nested(ret, Strings.class), b = nested(ret, Integers.class), c = nested(ret, Strings.class);
        return a == null && b == null && c == null;
    }

    public static boolean methodReturn() throws Exception {
        Method m = Supplier.class.getMethod("get");
        return ResolvableType.forMethodReturnType(m, Strings.class).getGeneric(0).getGeneric(0).resolve() == String.class
                && ResolvableType.forMethodReturnType(m, Integers.class).getGeneric(0).getGeneric(0).resolve() == Integer.class
                && ResolvableType.forMethodReturnType(m, Strings.class).getGeneric(0).getGeneric(0).resolve() == String.class;
    }

    public static boolean releasedSignature() {
        // Observe the real Spring interface's argument order and reified enum wildcard from the JVM.
        ParameterizedType p = (ParameterizedType) Convert.class.getGenericInterfaces()[0];
        Type[] args = p.getActualTypeArguments();
        ParameterizedType e = (ParameterizedType) args[0];
        WildcardType w = (WildcardType)e.getActualTypeArguments()[0];
        args[0] = String.class;
        w.getUpperBounds()[0] = Integer.class;
        return p.getRawType() == Converter.class && p.getOwnerType() == null && p.getActualTypeArguments()[1] == String.class
                && e.getRawType() == Enum.class && w.getUpperBounds()[0] == Object.class
                && ((ParameterizedType)Convert.class.getGenericInterfaces()[0]).getActualTypeArguments()[0].equals(e);
    }

    static boolean structure() {
        ResolvableType t = ResolvableType.forClass(Convert.class).as(Converter.class);
        ResolvableType e = t.getGeneric(0);
        return t.resolve() == Converter.class && t.getGenerics().length == 2 && t.getGeneric(1).resolve() == String.class
                && e.resolve() == Enum.class && e.getGenerics().length == 1 && e.getGeneric(0).getType() instanceof WildcardType;
    }

    public static boolean afterClear() {
        if (!structure()) return false;
        Type[] interfaces = Convert.class.getGenericInterfaces();
        ParameterizedType p = (ParameterizedType) interfaces[0];
        Type[] args = p.getActualTypeArguments();
        Type[] inner = ((ParameterizedType)args[0]).getActualTypeArguments();
        Type[] upper = ((WildcardType)inner[0]).getUpperBounds();
        interfaces[0] = String.class;
        args[0] = Integer.class;
        args[1] = Long.class;
        inner[0] = String.class;
        upper[0] = String.class;
        if (!structure()) return false;
        ResolvableType.clearCache();
        return structure();
    }
}
