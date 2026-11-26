import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.SimpleName;
import com.github.javaparser.printer.lexicalpreservation.LexicalPreservingPrinter;

public class PublicCaller {
    public static String observe(String[] a) {
        boolean field = a[0].equals("challenge");
        String src =
                field
                        ? "class A { int a[], keep; }"
                        : a[0].equals("control")
                                ? "class A { void m(String[][] a) {} }"
                                : "class A { void m(String[] a[]) {} }";
        var ast = StaticJavaParser.parse(src);
        LexicalPreservingPrinter.setup(ast);
        if (field)
            ast.findFirst(VariableDeclarator.class).orElseThrow().setName(new SimpleName("b"));
        else ast.findFirst(Parameter.class).orElseThrow().setName(new SimpleName("b"));
        String out = LexicalPreservingPrinter.print(ast);
        var read = StaticJavaParser.parse(out);
        if (field) {
            StringBuilder s = new StringBuilder(out);
            for (var f : read.findAll(VariableDeclarator.class))
                s.append("/")
                        .append(f.getNameAsString())
                        .append(":")
                        .append(f.getType().getArrayLevel());
            return s.toString();
        }
        var p = read.findFirst(Parameter.class).orElseThrow();
        return out + "/" + p.getNameAsString() + "/" + p.getType().getArrayLevel();
    }
}
