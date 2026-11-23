import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "ExactOrder#commons", "arguments", new String[]{"new String(new char[]{0xd800})", "new String(new char[]{0xd802})"}),
                fields("holds", ExactOrder.commons(new String(new char[]{0xd800}), new String(new char[]{0xd802}))), fields());
        row(1, fields("entry", "ExactOrder#commons", "arguments", new String[]{"new String(\"A\")", "new String(\"A\")"}),
                fields("holds", ExactOrder.commons(new String("A"), new String("A"))), fields());
        row(2, fields("entry", "ExactOrder#commons", "arguments", new String[]{"\"\"", "\"A\""}),
                fields("holds", ExactOrder.commons("", "A")), fields());
        row(3, fields("entry", "ExactOrder#commons", "arguments", new String[]{"\"A\"", "\"\""}),
                fields("holds", ExactOrder.commons("A", "")), fields());
        row(4, fields("entry", "ExactOrder#onlySign", "arguments", new String[]{"new String(\"A\")", "new String(\"A\")"}),
                fields("holds", ExactOrder.onlySign(new String("A"), new String("A"))), fields());
        row(5, fields("entry", "ExactOrder#onlySign", "arguments", new String[]{"\"\"", "\"A\""}),
                fields("holds", ExactOrder.onlySign("", "A")), fields());
        row(6, fields("entry", "ExactOrder#onlySign", "arguments", new String[]{"\"A\"", "\"\""}),
                fields("holds", ExactOrder.onlySign("A", "")), fields());
        row(7, fields("entry", "ExactOrder#onlySign", "arguments", new String[]{"new String(new char[]{0xd800})", "new String(new char[]{0xd802})"}),
                fields("holds", ExactOrder.onlySign(new String(new char[]{0xd800}), new String(new char[]{0xd802}))), fields());
        row(8, fields("entry", "ExactOrder#guava", "arguments", new String[]{"new String(new char[]{0xd800})", "new String(new char[]{0xd802})"}),
                fields("holds", ExactOrder.guava(new String(new char[]{0xd800}), new String(new char[]{0xd802}))), fields());
        row(9, fields("entry", "ExactOrder#guava", "arguments", new String[]{"new String(\"A\")", "new String(\"A\")"}),
                fields("holds", ExactOrder.guava(new String("A"), new String("A"))), fields());
        row(10, fields("entry", "ExactOrder#guava", "arguments", new String[]{"\"\"", "\"A\""}),
                fields("holds", ExactOrder.guava("", "A")), fields());
        row(11, fields("entry", "ExactOrder#guava", "arguments", new String[]{"\"A\"", "\"\""}),
                fields("holds", ExactOrder.guava("A", "")), fields());
        row(12, fields("entry", "ExactOrder#firstOnTie", "arguments", new String[]{"new String(new char[]{0xd800})", "new String(new char[]{0xd802})"}),
                fields("holds", ExactOrder.firstOnTie(new String(new char[]{0xd800}), new String(new char[]{0xd802}))), fields());
        row(13, fields("entry", "ExactOrder#firstOnTie", "arguments", new String[]{"new String(\"A\")", "new String(\"A\")"}),
                fields("holds", ExactOrder.firstOnTie(new String("A"), new String("A"))), fields());
        row(14, fields("entry", "ExactOrder#firstOnTie", "arguments", new String[]{"\"\"", "\"A\""}),
                fields("holds", ExactOrder.firstOnTie("", "A")), fields());
        row(15, fields("entry", "ExactOrder#firstOnTie", "arguments", new String[]{"\"A\"", "\"\""}),
                fields("holds", ExactOrder.firstOnTie("A", "")), fields());
        row(16, fields("entry", "ExactOrder#secondOnTie", "arguments", new String[]{"new String(new char[]{0xd800})", "new String(new char[]{0xd802})"}),
                fields("holds", ExactOrder.secondOnTie(new String(new char[]{0xd800}), new String(new char[]{0xd802}))), fields());
        row(17, fields("entry", "ExactOrder#secondOnTie", "arguments", new String[]{"new String(\"A\")", "new String(\"A\")"}),
                fields("holds", ExactOrder.secondOnTie(new String("A"), new String("A"))), fields());
        row(18, fields("entry", "ExactOrder#direct", "arguments", new String[]{"new String(new char[]{0xd800})", "new String(new char[]{0xd802})"}),
                fields("holds", ExactOrder.direct(new String(new char[]{0xd800}), new String(new char[]{0xd802}))), fields());
        row(19, fields("entry", "ExactOrder#direct", "arguments", new String[]{"new String(\"A\")", "new String(\"A\")"}),
                fields("holds", ExactOrder.direct(new String("A"), new String("A"))), fields());
        row(20, fields("entry", "ExactOrder#direct", "arguments", new String[]{"\"\"", "\"A\""}),
                fields("holds", ExactOrder.direct("", "A")), fields());
        row(21, fields("entry", "ExactOrder#direct", "arguments", new String[]{"\"A\"", "\"\""}),
                fields("holds", ExactOrder.direct("A", "")), fields());
        row(22, fields("entry", "ExactOrder#sameReference", "arguments", new String[]{"\"\""}),
                fields("holds", ExactOrder.sameReference("")), fields());
        row(23, fields("entry", "ExactOrder#sameReference", "arguments", new String[]{"new String(new char[]{0xd800})"}),
                fields("holds", ExactOrder.sameReference(new String(new char[]{0xd800}))), fields());
    }
}
