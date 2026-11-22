package springwork;

import static springwork.BindingHistory.*;

public final class BindingChecks {
    public static int beans(int code) { return matches(trace(code, false), code, false) ? 1 : 0; }
    public static int ledger(int code) { return matches(trace(code, false), code, true) ? 1 : 0; }
}
