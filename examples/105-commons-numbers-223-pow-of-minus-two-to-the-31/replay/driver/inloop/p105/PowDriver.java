package inloop.p105;

import org.apache.commons.numbers.core.ArithmeticUtils;

/** 105's concrete control: it calls the original ArithmeticUtils.pow(int, int) of whichever commons-numbers-core
 * classes are on the class path, once per probe, and prints one JSON line per probe: the arguments and the outcome as
 * the JVM gave it (the returned int, or the exception's class). It decides nothing; controls/oracle.py reads the
 * lines. It maps, normalizes and replaces nothing, so the original bytecode decides.
 *
 * <p>Arguments come in pairs, k then e, each a decimal int ({@code python3 -I controls/oracle.py argv} prints them).
 * Compiled with {@code --release 21} against one revision's class; the method's descriptor is the same at both
 * commits, so one driver JAR runs on either. Only a RuntimeException is recorded as an outcome, by class (the message
 * is not observed). An Error ends the run, and the oracle reports the probes it lacks as an incomplete replay, never
 * as a result. */
public final class PowDriver {
    private PowDriver() {
    }

    public static void main(String[] args) {
        if (args.length % 2 != 0) {
            throw new IllegalArgumentException("arguments come in pairs, k then e");
        }
        for (int i = 0; i < args.length; i += 2) {
            int k = Integer.parseInt(args[i]);
            int e = Integer.parseInt(args[i + 1]);
            String outcome;
            try {
                outcome = "\"returned\",\"value\":" + ArithmeticUtils.pow(k, e);
            } catch (RuntimeException x) {
                outcome = "\"threw\",\"exception\":\"" + x.getClass().getName() + "\"";
            }
            System.out.println("{\"k\":" + k + ",\"e\":" + e + ",\"outcome\":" + outcome + "}");
        }
    }
}
