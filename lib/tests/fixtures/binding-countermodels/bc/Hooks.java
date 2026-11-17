package bc;

import java.util.function.IntSupplier;

/** A class whose static holds a lambda of its own, and a method that puts another of its lambdas there. */
public class Hooks {
    public static IntSupplier hook = () -> 1;

    public static void install(int n) {
        hook = () -> n;
    }
}
