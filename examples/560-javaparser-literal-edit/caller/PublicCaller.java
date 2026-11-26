import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.expr.StringLiteralExpr;
import com.github.javaparser.printer.lexicalpreservation.LexicalPreservingPrinter;

public class PublicCaller {
    public static String observe(String[] a) {
        String source = "class A { /* neighbour: a */ String v   =   \"a\"; }";
        var unit = StaticJavaParser.parse(source);
        LexicalPreservingPrinter.setup(unit);
        var literal = unit.findFirst(StringLiteralExpr.class).orElseThrow();
        String requested =
                switch (a[0]) {
                    case "control" -> "a";
                    case "challenge" -> "b\n\"";
                    default -> "b";
                };
        literal.setString(requested);
        String text = LexicalPreservingPrinter.print(unit);
        String actual =
                StaticJavaParser.parse(text)
                        .findFirst(StringLiteralExpr.class)
                        .orElseThrow()
                        .asString();
        if (a[0].equals("challenge"))
            return literal.asString().equals(requested)
                    + "/"
                    + actual.equals(requested)
                    + "/"
                    + text.contains("/* neighbour: a */");
        if (a[0].equals("control")) return text.equals(source) + "/" + actual;
        return literal.asString()
                + "/"
                + actual
                + "/"
                + text.equals(source.replace("\"a\"", "\"b\""));
    }
}
