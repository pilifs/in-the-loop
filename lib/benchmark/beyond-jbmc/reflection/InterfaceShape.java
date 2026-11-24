// InterfaceShape.java — no framework dependency
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;

public final class InterfaceShape {
    interface Convert<T, U> {}
    static final class C implements Convert<Enum<?>, String> {}

    public static boolean intact() {
        Type[] interfaces = C.class.getGenericInterfaces();
        if (interfaces == null || interfaces.length != 1
                || !(interfaces[0] instanceof ParameterizedType)) return false;
        ParameterizedType original = (ParameterizedType) interfaces[0];
        interfaces[0] = String.class;
        return original.getRawType() == Convert.class
                && C.class.getGenericInterfaces()[0].equals(original)
                && original.getActualTypeArguments()[1] == String.class;
    }

    public static void expected() { assert intact(); }
    public static void inverted() { assert !intact(); }
}
