package mr;

/** The class file a multi-release JAR holds for Java 17 on, under META-INF/versions/17: what a JVM 17+ loads. */
public class Release {
    public static int a;

    static {
        a = 2;
    }

    public static int get() {
        return a * 10;
    }
}
