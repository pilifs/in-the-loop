package lib;

/** A library's mutable static: what one version writes, a version run after it in the same JVM reads. */
public final class Flags {
    private Flags() {}

    public static boolean on;
}
