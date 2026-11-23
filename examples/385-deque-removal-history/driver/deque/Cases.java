import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "history", "arguments", new String[]{"false"}),
                fields("holds", DequeRemoval.history(false)), fields());
        row(1, fields("entry", "history", "arguments", new String[]{"true"}),
                fields("holds", DequeRemoval.history(true)), fields());
        row(2, fields("entry", "stillReturns", "arguments", new String[]{}),
                fields("holds", DequeRemoval.stillReturns()), fields());
        row(3, fields("entry", "singleton", "arguments", new String[]{"false"}),
                fields("holds", DequeRemoval.singleton(false)), fields());
        row(4, fields("entry", "singleton", "arguments", new String[]{"true"}),
                fields("holds", DequeRemoval.singleton(true)), fields());
        row(5, fields("entry", "filtered", "arguments", new String[]{"false"}),
                fields("holds", DequeRemoval.filtered(false)), fields());
        row(6, fields("entry", "filtered", "arguments", new String[]{"true"}),
                fields("holds", DequeRemoval.filtered(true)), fields());
    }
}
