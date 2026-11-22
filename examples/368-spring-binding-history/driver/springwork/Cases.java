package springwork;

import org.springframework.beans.MutablePropertyValues;
import org.springframework.validation.DataBinder;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) {
        BindingHistory.Session s = new BindingHistory.Session(true);
        s.edit(1);
        DataBinder fresh = new DataBinder(s.draft);
        fresh.bind(new MutablePropertyValues().add("primary.count", "7"));
        if (fresh.getBindingResult().getErrorCount() != 0 || s.sample().errors() != 1
                || s.draft.getBackup().getCount() != 7) throw new AssertionError("fresh binder lifetime");
        if (BindingHistory.matches(BindingHistory.trace(0, true), 0, false))
            throw new AssertionError("skipping the last edit escaped the bean observer");
        for (int code = 0; code < 12; code++) {
            var trace = BindingHistory.trace(code, false);
            Object[][] beans = new Object[3][], errors = new Object[3][];
            for (int step = 0; step < 3; step++) {
                beans[step] = trace[step].bean();
                errors[step] = trace[step].error();
            }
            row(code, fields("shared", code >= 6, "order", BindingHistory.order(code)),
                    fields("beans", beans, "ledger", errors),
                    fields("beans", BindingChecks.beans(code), "ledger", BindingChecks.ledger(code)));
        }
    }
}
