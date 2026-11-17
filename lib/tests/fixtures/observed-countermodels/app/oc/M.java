package oc;

/**
 * The entry points of the observed-initializer countermodels, and a {@code main} that runs one of them on a JVM and
 * prints what it returns: {@code java -cp CLASSES oc.M crossed}.
 */
public class M {
    /** Reads A's static, which initializes A, then B's: 1 on a JVM, whose A.<clinit> wrote it. */
    public static int crossed() {
        int k = A.k;
        return B.x;
    }

    /** The first code unit of "I" lowered when Lowered was initialized: 105 in English, 305 in Turkish. */
    public static int lowered() {
        return Lowered.I.charAt(0);
    }

    /** The length of the property Configured read: 6 ("absent") where it is not set. */
    public static int configured() {
        return Configured.VALUE.length();
    }

    /** What the multi-release library's class says: 1 from its base class file, 20 from the one for Java 17 on. */
    public static int released() {
        return mr.Release.get();
    }

    /** The multi-release library's static itself: 1 after its base initializer, 2 after the one for Java 17 on. */
    public static int releasedField() {
        return mr.Release.a;
    }

    /** An empty AttributesImpl's length: 0 from the JDK's java.xml, whatever a class path holds of the class. */
    public static int shadowed() {
        return new org.xml.sax.helpers.AttributesImpl().getLength();
    }

    public static void main(String[] args) {
        int result = switch (args[0]) {
            case "crossed" -> crossed();
            case "lowered" -> lowered();
            case "configured" -> configured();
            case "released" -> released();
            case "releasedField" -> releasedField();
            case "shadowed" -> shadowed();
            default -> throw new IllegalArgumentException(args[0]);
        };
        System.out.println(args[0] + "=" + result);
    }
}
