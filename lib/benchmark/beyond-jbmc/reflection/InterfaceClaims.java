import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.lang.reflect.WildcardType;

public final class InterfaceClaims {
    public static boolean intact() { return InterfaceShape.intact(); }
    public static boolean inverse() { return !InterfaceShape.intact(); }

    public static boolean defensiveCopies() {
        Type[] interfaces = InterfaceShape.C.class.getGenericInterfaces();
        ParameterizedType p = (ParameterizedType)interfaces[0];
        Type[] args = p.getActualTypeArguments();
        ParameterizedType e = (ParameterizedType)args[0];
        Type[] inner = e.getActualTypeArguments();
        WildcardType w = (WildcardType)inner[0];
        Type[] upper = w.getUpperBounds();
        interfaces[0] = String.class;
        args[0] = Integer.class;
        args[1] = Long.class;
        inner[0] = String.class;
        upper[0] = Double.class;
        ParameterizedType again = (ParameterizedType)InterfaceShape.C.class.getGenericInterfaces()[0];
        Type[] fresh = again.getActualTypeArguments();
        ParameterizedType nested = (ParameterizedType)fresh[0];
        WildcardType wildcard = (WildcardType)nested.getActualTypeArguments()[0];
        return again.getRawType() == InterfaceShape.Convert.class && again.getOwnerType() == InterfaceShape.class
                && again.equals(p) && fresh.length == 2 && fresh[1] == String.class
                && nested.getRawType() == Enum.class && nested.getOwnerType() == null
                && wildcard.equals(w) && wildcard.getUpperBounds().length == 1
                && wildcard.getUpperBounds()[0] == Object.class && wildcard.getLowerBounds().length == 0;
    }
}
