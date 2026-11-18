package app;

/** The previous version's initializer sets Counter.v to 2. It declares a default method, so making an Item initializes it. */
public interface Tagged {
    int SEED = Counter.set(2);

    default int tag() {
        return SEED;
    }
}
