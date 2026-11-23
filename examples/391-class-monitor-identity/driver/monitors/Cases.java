import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "matched", "arguments", new String[]{}),
                fields("holds", MonitorIdentity.matched()), fields());
        row(1, fields("entry", "synchronizedMethod", "arguments", new String[]{}),
                fields("holds", MonitorIdentity.synchronizedMethod()), fields());
        row(2, fields("entry", "workerFirst", "arguments", new String[]{}),
                fields("holds", MonitorIdentity.workerFirst()), fields());
    }
}
