import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "history", "arguments", new String[]{"null"}),
                fields("holds", ConstructorPhase.history(null)), fields());
        row(1, fields("entry", "history", "arguments", new String[]{"\"\""}),
                fields("holds", ConstructorPhase.history("")), fields());
        row(2, fields("entry", "history", "arguments", new String[]{"\"A\""}),
                fields("holds", ConstructorPhase.history("A")), fields());
        row(3, fields("entry", "history", "arguments", new String[]{"\"\\uD800\""}),
                fields("holds", ConstructorPhase.history("\uD800")), fields());
        row(4, fields("entry", "history", "arguments", new String[]{"\"\\uDC00\""}),
                fields("holds", ConstructorPhase.history("\uDC00")), fields());
        row(5, fields("entry", "history", "arguments", new String[]{"\"\\uDBFF\\uDFFF\""}),
                fields("holds", ConstructorPhase.history("\uDBFF\uDFFF")), fields());
        row(6, fields("entry", "emptySkips", "arguments", new String[]{}),
                fields("holds", ConstructorPhase.emptySkips()), fields());
        row(7, fields("entry", "alreadyInitialized", "arguments", new String[]{}),
                fields("holds", ConstructorPhase.alreadyInitialized()), fields());
    }
}
