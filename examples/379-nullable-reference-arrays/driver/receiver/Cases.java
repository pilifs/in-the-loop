import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "exact", "arguments", new String[]{"false"}),
                fields("holds", ReceiverScope.exact(false)), fields());
        row(1, fields("entry", "exact", "arguments", new String[]{"true"}),
                fields("holds", ReceiverScope.exact(true)), fields());
        row(2, fields("entry", "parentOrChild", "arguments", new String[]{"0"}),
                fields("holds", ReceiverScope.parentOrChild(0)), fields());
        row(3, fields("entry", "parentOrChild", "arguments", new String[]{"1"}),
                fields("holds", ReceiverScope.parentOrChild(1)), fields());
        row(4, fields("entry", "parentOrChild", "arguments", new String[]{"2"}),
                fields("holds", ReceiverScope.parentOrChild(2)), fields());
    }
}
