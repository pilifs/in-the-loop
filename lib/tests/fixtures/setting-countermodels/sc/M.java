package sc;

/**
 * The entry points of the countermodels of an observation bound to the settings it read, and a {@code main} that runs one on a JVM and prints
 * what it returns: {@code java -cp CLASSES sc.M mapped}.
 */
public class M {
    /** The length of the property Mapped read: 6 ("absent") where sc.value is not set. */
    public static int mapped() {
        return Mapped.VALUE.length();
    }

    /** The length of the property Kept read: 6 ("absent") where sc.value is not set. */
    public static int kept() {
        return Kept.VALUE.length();
    }

    /** The length of the environment variable Looked read: 6 ("absent") where SC_VALUE is not set. */
    public static int looked() {
        return Looked.VALUE.length();
    }

    /** The processors the JVM may use when Counted was initialized. */
    public static int counted() {
        return Counted.CPUS;
    }

    /** The length of the working directory's path when Rooted was initialized. */
    public static int rooted() {
        return Rooted.DIR.length();
    }

    /** The bytes of "é" in the default charset when Encoded was initialized: 2 in UTF-8, the default since JDK 18. */
    public static int encoded() {
        return Encoded.N;
    }

    public static void main(String[] args) {
        int result = switch (args[0]) {
            case "mapped" -> mapped();
            case "kept" -> kept();
            case "looked" -> looked();
            case "counted" -> counted();
            case "rooted" -> rooted();
            case "encoded" -> encoded();
            default -> throw new IllegalArgumentException(args[0]);
        };
        System.out.println(args[0] + "=" + result);
    }
}
