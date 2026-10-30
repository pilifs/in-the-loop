package net.terminalvalue.contracts.fixtures;

import java.time.Instant;
import java.util.UUID;

/** A class whose bytecode exercises a few capabilities, for the capability contract tests. */
public final class Capable {

    private Capable() {}

    public static Object loadByName(String name) throws ReflectiveOperationException {
        return Class.forName(name).getDeclaredConstructor().newInstance();
    }

    public static String stamp() {
        return Instant.now() + " " + UUID.randomUUID();
    }

    public static String home() {
        return System.getenv("HOME");
    }

    public static int pure(int x) {
        return Math.abs(x) + 1;
    }
}
