package upstream.driver;

import upstream.adapter.PowAdapter;

/** The upstream-build check's concrete control. Each argument is one input, a JSON array of two ints
 * ({@code [-2, 31]}, the oracle's PROBES as runtime passes them). It prints one JSON line per input: the input as
 * given, and the outcome as the JVM gave it (a value, or the exception's class). It decides nothing: the oracle reads
 * these lines. An argument it can't read stops it with no line for that input, an incomplete replay. */
public final class PowDriver {
    private PowDriver() {
    }

    public static void main(String[] args) {
        for (String arg : args) {
            int[] input = pair(arg);
            String outcome;
            try {
                outcome = "\"returned\",\"value\":" + PowAdapter.pow(input[0], input[1]);
            } catch (RuntimeException e) {
                outcome = "\"threw\",\"exception\":\"" + e.getClass().getName() + "\"";
            }
            System.out.println("{\"input\":" + arg + ",\"outcome\":" + outcome + "}");
        }
    }

    private static int[] pair(String text) {
        String inside = text.strip();
        if (!inside.startsWith("[") || !inside.endsWith("]")) {
            throw new IllegalArgumentException("input " + text + ": not a JSON array");
        }
        String[] parts = inside.substring(1, inside.length() - 1).split(",");
        if (parts.length != 2) {
            throw new IllegalArgumentException("input " + text + ": not two values");
        }
        return new int[] {Integer.parseInt(parts[0].strip()), Integer.parseInt(parts[1].strip())};
    }
}
