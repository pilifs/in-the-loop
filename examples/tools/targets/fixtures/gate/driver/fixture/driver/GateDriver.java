package fixture.driver;

import fixture.adapter.GateAdapter;

/** The concrete control: one JSON line per input, the outcome as the JVM gave it (a value or the exception's class).
 * It decides nothing: the oracle reads these lines. */
public final class GateDriver {
    private GateDriver() {
    }

    public static void main(String[] args) {
        for (String arg : args) {
            int code = Integer.parseInt(arg);
            String outcome;
            try {
                outcome = "\"returned\",\"value\":" + GateAdapter.allowed(code);
            } catch (RuntimeException e) {
                outcome = "\"threw\",\"exception\":\"" + e.getClass().getName() + "\"";
            }
            System.out.println("{\"input\":" + code + ",\"outcome\":" + outcome + "}");
        }
    }
}
