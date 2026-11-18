package app;

/** The new version's initializer sets Counter.v to 1. It declares a default method, so making an Item initializes it. */
public interface Tagged {
    int SEED = Counter.set(1);

    default int tag() {
        return SEED;
    }
}
