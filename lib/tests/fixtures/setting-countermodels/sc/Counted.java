package sc;

/** The processors the JVM may use, as a pool's size is often taken: a setting of the machine and the JVM's flags. */
public class Counted {
    public static final int CPUS = Runtime.getRuntime().availableProcessors();
}
