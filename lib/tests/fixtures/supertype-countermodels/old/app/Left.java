package app;

/** The same in both versions: a default method the previous version's Mixed takes. */
public interface Left {
    default int m(int k) {
        return k > 1000 ? 2 : 0;
    }
}
