import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "compatible", "arguments", new String[]{"0"}),
                fields("holds", GsonRequestedClass.compatible(0)), fields());
        row(1, fields("entry", "compatible", "arguments", new String[]{"1"}),
                fields("holds", GsonRequestedClass.compatible(1)), fields());
        row(2, fields("entry", "compatible", "arguments", new String[]{"2"}),
                fields("holds", GsonRequestedClass.compatible(2)), fields());
        row(3, fields("entry", "compatible", "arguments", new String[]{"3"}),
                fields("holds", GsonRequestedClass.compatible(3)), fields());
        row(4, fields("entry", "compatible", "arguments", new String[]{"4"}),
                fields("holds", GsonRequestedClass.compatible(4)), fields());
        row(5, fields("entry", "syntax", "arguments", new String[]{"0"}),
                fields("holds", GsonRequestedClass.syntax(0)), fields());
        row(6, fields("entry", "syntax", "arguments", new String[]{"1"}),
                fields("holds", GsonRequestedClass.syntax(1)), fields());
        row(7, fields("entry", "syntax", "arguments", new String[]{"2"}),
                fields("holds", GsonRequestedClass.syntax(2)), fields());
        row(8, fields("entry", "syntax", "arguments", new String[]{"3"}),
                fields("holds", GsonRequestedClass.syntax(3)), fields());
    }
}
