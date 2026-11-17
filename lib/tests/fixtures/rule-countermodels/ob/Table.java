package ob;

/** An interface whose initializer makes an array: a JVM initializes it at the first read of T. */
public interface Table {
    int[] T = {0};
}
