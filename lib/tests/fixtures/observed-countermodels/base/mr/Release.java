package mr;

/** The base class file of a multi-release JAR: what a JVM before Java 17 loads. */
public class Release {
    public static int a;

    static {
        a = 1;
    }

    public static int get() {
        return a;
    }
}
