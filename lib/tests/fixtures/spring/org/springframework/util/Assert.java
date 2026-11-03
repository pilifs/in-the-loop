// A stand-in for the framework class of the same name, so that the fixtures compile without the framework on the
// class path. jvmcontract knows what each method throws.
package org.springframework.util;

public abstract class Assert {
    public static void hasText(String text, String message) {
        if (text == null || text.isBlank()) {
            throw new IllegalArgumentException(message);
        }
    }

    public static void state(boolean expression, String message) {
        if (!expression) {
            throw new IllegalStateException(message);
        }
    }
}
