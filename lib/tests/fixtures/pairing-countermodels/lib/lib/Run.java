package lib;

import java.util.function.Supplier;

/** How a countermodel's {@code main} prints one outcome: a String by its code units, an exception by its class. */
public final class Run {
    private Run() {}

    public static String describe(Supplier<Object> call) {
        try {
            Object result = call.get();
            if (result instanceof String s) {
                return s.chars().mapToObj(Integer::toString).reduce((a, b) -> a + "," + b).orElse("");
            }
            return String.valueOf(result);
        } catch (RuntimeException e) {
            return e.getClass().getSimpleName();
        }
    }
}
