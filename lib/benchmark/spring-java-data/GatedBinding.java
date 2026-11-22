package springwork;

import static org.intheloop.controls.Grid.*;

/** Decisions and bean state are read through the public Spring application after every attempted edit. */
public final class GatedBinding {
    static Object[] trace(boolean shared, int code, int mode) {
        var session = new BindingHistory.Session(shared);
        Object[] trace = new Object[3];
        int prefix = code & 16;
        for (int step = 0; step < 3; step++) {
            int roles = mode == 0 ? (step == 2 ? code : prefix | (step == 0 ? 2 : 8))
                    : prefix | (mode == 1 ? new int[]{1,4,2}[step] : new int[]{1,2,8}[step]);
            boolean grant = RoleApplication.decide(roles, true, false);
            if (mode == 0 && step < 2 || grant) session.edit(step);
            var snapshot = session.sample();
            trace[step] = new Object[]{grant,session.edits,snapshot.bean(),snapshot.error()};
        }
        return trace;
    }

    public static int primary(int code) {
        boolean shared = code >= 32;
        Object[] steps = trace(shared, code % 32, 0);
        for (int i = 0; i < 3; i++) {
            boolean grant = i < 2 || (code & 11) != 0;
            boolean good = i == 2 && grant;
            int count = good ? 7 : 1, backup = shared ? count : 1;
            Object[] step = (Object[]) steps[i], bean = (Object[]) step[2], ledger = (Object[]) step[3];
            if (!Boolean.valueOf(grant).equals(step[0]) || !Integer.valueOf(i == 2 && !grant ? 2 : i+1).equals(step[1])
                    || !"Kim".equals(bean[0]) || !Integer.valueOf(count).equals(bean[1])
                    || !(shared ? "Kim" : "initial").equals(bean[2]) || !Integer.valueOf(backup).equals(bean[3])
                    || !Boolean.valueOf(shared).equals(bean[4]) || !Boolean.TRUE.equals(bean[5])
                    || !Integer.valueOf(i == 0 ? 0 : 1).equals(ledger[0])
                    || (i == 0 ? ledger[1] != null || ledger[2] != null
                               : !"backup.count".equals(ledger[1]) || !"oops".equals(ledger[2]))
                    || !Integer.valueOf(count).equals(ledger[3]) || !Integer.valueOf(backup).equals(ledger[4])) return 0;
        }
        return 1;
    }

    public static void main(String[] args) {
        for (int i = 0; i < 64; i++)
            row(i,fields("shared",i >= 32,"prefix",RoleApplication.prefix(i % 32),"mask",i % 16),
                trace(i >= 32,i % 32,0),null);
        int id = 64;
        for (boolean shared : new boolean[]{false,true})
            for (int prefix : new int[]{0,16}) for (int mode : new int[]{1,2})
                row(id++,fields("shared",shared,"prefix",RoleApplication.prefix(prefix),"history",mode),
                    trace(shared,prefix,mode),null);
    }
}
