package app;

/** The same in both versions: a default method the new version's Mixed takes. */
public interface Right {
    default int m(int k) {
        return k > 1000 ? 1 : 0;
    }
}
