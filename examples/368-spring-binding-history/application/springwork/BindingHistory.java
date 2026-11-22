package springwork;

import org.springframework.beans.MutablePropertyValues;
import org.springframework.validation.BindingResult;
import org.springframework.validation.DataBinder;
import org.springframework.validation.FieldError;

/** A new session owns both the bean and the one binder reused throughout its history. */
public final class BindingHistory {
    public static final class Child {
        private String name = "initial";
        private int count = 1;
        public String getName() { return name; }
        public void setName(String value) { name = value; }
        public int getCount() { return count; }
        public void setCount(int value) { count = value; }
    }

    public static final class Draft {
        private final Child primary = new Child();
        private final Child backup;
        Draft(boolean shared) { backup = shared ? primary : new Child(); }
        public Child getPrimary() { return primary; }
        public Child getBackup() { return backup; }
    }

    public static final class Session {
        public final Draft draft;
        public final DataBinder binder;
        private final Child originalPrimary;
        private final Child originalBackup;
        public int edits;

        public Session(boolean shared) {
            draft = new Draft(shared);
            originalPrimary = draft.getPrimary();
            originalBackup = draft.getBackup();
            binder = new DataBinder(draft);
        }

        public void edit(int edit) {
            String field = edit == 0 ? "primary.name" : edit == 1 ? "backup.count" : "primary.count";
            String value = edit == 0 ? "Kim" : edit == 1 ? "oops" : "7";
            binder.bind(new MutablePropertyValues().add(field, value));
            edits++;
        }

        public Snapshot sample() {
            Child primary = draft.getPrimary(), backup = draft.getBackup();
            BindingResult result = binder.getBindingResult();
            FieldError error = result.getFieldError();
            return new Snapshot(primary.getName(), primary.getCount(), backup.getName(), backup.getCount(),
                    primary == backup, primary == originalPrimary && backup == originalBackup, result.getErrorCount(),
                    error == null ? null : error.getField(), error == null ? null : error.getRejectedValue());
        }
    }

    public record Snapshot(String name, int count, String backupName, int backupCount, boolean shared,
                           boolean originalChildren, int errors, String errorField, Object rejected) {
        public Object[] bean() { return new Object[]{name, count, backupName, backupCount, shared, originalChildren}; }
        public Object[] error() { return new Object[]{errors, errorField, rejected, count, backupCount}; }
    }

    private static final int[][] ORDERS = {{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
    public static int[] order(int code) { return ORDERS[code % 6]; }

    public static Snapshot[] trace(int code, boolean stopAfterError) {
        Session s = new Session(code >= 6);
        Snapshot[] prefix = new Snapshot[3];
        for (int i = 0; i < 3; i++) {
            if (!stopAfterError || !s.binder.getBindingResult().hasErrors()) s.edit(order(code)[i]);
            prefix[i] = s.sample();
        }
        return prefix;
    }

    public static boolean matches(Snapshot[] prefix, int code, boolean ledger) {
        boolean shared = code >= 6, renamed = false, invalid = false, updated = false;
        for (int i = 0; i < 3; i++) {
            int edit = order(code)[i];
            renamed |= edit == 0;
            invalid |= edit == 1;
            updated |= edit == 2;
            Snapshot s = prefix[i];
            if (s.count != (updated ? 7 : 1) || s.backupCount != (shared && updated ? 7 : 1)) return false;
            if (ledger) {
                if (s.errors != (invalid ? 1 : 0)) return false;
                if (invalid ? !("backup.count".equals(s.errorField) && "oops".equals(s.rejected))
                            : s.errorField != null || s.rejected != null) return false;
            } else if (s.shared != shared || !s.originalChildren
                    || !(renamed ? "Kim" : "initial").equals(s.name)
                    || !(renamed && shared ? "Kim" : "initial").equals(s.backupName)) return false;
        }
        return true;
    }

}
