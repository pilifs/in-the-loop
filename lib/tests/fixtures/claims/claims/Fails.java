package claims;

/** An initializer that throws, whatever runs it. */
final class Fails {
    private Fails() {}

    static int MARK;

    static {
        if (MARK == 0) {
            throw new IllegalStateException("no table");
        }
    }
}
