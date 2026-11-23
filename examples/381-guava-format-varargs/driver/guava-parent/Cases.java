import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "retained", "arguments", new String[]{"false"}),
                fields("holds", FormatHistory.retained(false)), fields());
        row(1, fields("entry", "retained", "arguments", new String[]{"true"}),
                fields("holds", FormatHistory.retained(true)), fields());
        row(2, fields("entry", "parentBehavior", "arguments", new String[]{"false"}),
                fields("holds", FormatHistory.parentBehavior(false)), fields());
        row(3, fields("entry", "parentBehavior", "arguments", new String[]{"true"}),
                fields("holds", FormatHistory.parentBehavior(true)), fields());
    }
}
