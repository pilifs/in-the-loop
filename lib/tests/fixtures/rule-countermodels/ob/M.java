package ob;

/**
 * The entry points of the countermodels of an observation bound to what it was observed on, and a {@code main} that runs one on a JVM and prints what
 * it returns: {@code java -cp CLASSES ob.M inherited}.
 */
public class M {
    /** Reads Derived's static, which initializes Base and then Derived, then Base's: 1 on a JVM. */
    public static int inherited() {
        int k = Derived.k;
        return Base.x;
    }

    /** Reads Filled's static, then the interface's cell its initializer wrote: 5 on a JVM. */
    public static int filled() {
        int k = Filled.k;
        return Table.T[0];
    }

    /** The length of the property Bypassed read: 6 ("absent") where ob.value is not set. */
    public static int bypassed() {
        return Bypassed.VALUE.length();
    }

    /** The default time zone's raw offset in hours: 0 under -Duser.timezone=UTC, 9 under Asia/Tokyo. */
    public static int zoned() {
        return Zoned.OFFSET;
    }

    /** The length of the environment variable Environ read: 6 ("absent") where OB_VALUE is not set. */
    public static int environ() {
        return Environ.VALUE.length();
    }

    public static void main(String[] args) {
        int result = switch (args[0]) {
            case "inherited" -> inherited();
            case "filled" -> filled();
            case "bypassed" -> bypassed();
            case "zoned" -> zoned();
            case "environ" -> environ();
            default -> throw new IllegalArgumentException(args[0]);
        };
        System.out.println(args[0] + "=" + result);
    }
}
