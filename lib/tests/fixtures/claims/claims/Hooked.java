package claims;

import java.util.function.IntSupplier;

/**
 * An initializer that initializes another class, whose state holds a lambda ({@link Hooks}), as Spring's
 * CachedIntrospectionResults initializes ReflectionUtils, whose method filters are lambdas. A JVM names a lambda's
 * hidden class with an address (`claims.Hooks$$Lambda/0x...`) that differs from one run to the next: here the run
 * that observes Hooked defines two lambdas before Hooks', and the run of Hooks alone none. The observation's
 * binding compares Hooks' state in the two runs, and must not take the address for a write ({@link Hooking}).
 */
final class Hooked {
    private Hooked() {}

    static final Runnable OWN = () -> {};
    static final IntSupplier MORE = () -> 1;
    static int k = Hooks.count + 4;
}

final class Hooks {
    private Hooks() {}

    static final Runnable HOOK = () -> {};
    static int count = 3;
}

/** Reads what Hooked's observed initializer left. */
final class Hooking {
    private Hooking() {}

    public static boolean hooked() {
        return Hooked.k == 7;
    }
}
