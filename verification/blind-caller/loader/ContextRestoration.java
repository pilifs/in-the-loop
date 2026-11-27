package trial;

import styles.World;

public final class ContextRestoration {
    public static void main(String[] args) throws Exception {
        Thread current = Thread.currentThread();
        ClassLoader prior = current.getContextClassLoader();
        ClassLoader marker = new ClassLoader("outer marker", prior) {};
        current.setContextClassLoader(marker);
        try {
            for (int code = 0; code < 16; code++) {
                World.sequence(code);
                if (current.getContextClassLoader() != marker) {
                    throw new AssertionError("original caller lost its loader on normal return");
                }
            }
            try {
                // The first call has a valid profile; the second profile index is negative.
                World.sequence(-1);
                throw new AssertionError("the second call should fail");
            } catch (ArrayIndexOutOfBoundsException expected) {
                if (current.getContextClassLoader() != marker) {
                    throw new AssertionError("original caller lost its loader on abrupt return");
                }
                System.out.println("16 normal returns and 1 " + expected.getClass().getSimpleName() + " restored the same loader");
            }
        } finally {
            current.setContextClassLoader(prior);
        }
    }
}
