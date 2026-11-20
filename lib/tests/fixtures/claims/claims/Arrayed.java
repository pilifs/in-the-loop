package claims;

/**
 * {@code Class.isArray()}, as Spring's {@code ObjectUtils.isArray} asks it of the class of the value a binding error
 * records (example 286): of class literals, fresh arrays and an opaque JDK receiver. {@code main} prints what a
 * JVM answers.
 */
public class Arrayed {
    /** A String's class is no array class, nor is this one; {@code String[]}'s and {@code int[][]}'s are. */
    public static boolean arrayed(String s) {
        return !s.getClass().isArray() && String[].class.isArray() && int[][].class.isArray() && !Arrayed.class.isArray();
    }

    /** The class of an array is an array class: true on a JVM. */
    public static boolean ofAnArray() {
        return new int[0].getClass().isArray();
    }

    /** A class is assignable from itself: true on a JVM. */
    public static boolean assignableOfAnArray() {
        Class<?> c = new int[0].getClass();
        return c.isAssignableFrom(c);
    }

    public static boolean opaqueIsArray() {
        return !new Object().getClass().isArray();
    }

    public static boolean opaqueAssignable() {
        Class<?> c = new Object().getClass();
        return c.isAssignableFrom(c);
    }

    public static void main(String[] args) {
        System.out.println(arrayed("a") + " " + ofAnArray() + " " + assignableOfAnArray() + " " + opaqueIsArray() + " " + opaqueAssignable());
    }
}
