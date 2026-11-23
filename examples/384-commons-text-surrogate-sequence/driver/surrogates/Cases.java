import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "translate", "arguments", new String[]{"'A'", "'B'", "true"}),
                fields("holds", SurrogateUnits.translate('A', 'B', true)), fields());
        row(1, fields("entry", "translate", "arguments", new String[]{"'A'", "'B'", "false"}),
                fields("holds", SurrogateUnits.translate('A', 'B', false)), fields());
        row(2, fields("entry", "translate", "arguments", new String[]{"(char)0xDBFF", "(char)0xDFFF", "true"}),
                fields("holds", SurrogateUnits.translate((char)0xDBFF, (char)0xDFFF, true)), fields());
        row(3, fields("entry", "translate", "arguments", new String[]{"(char)0xDBFF", "(char)0xDFFF", "false"}),
                fields("holds", SurrogateUnits.translate((char)0xDBFF, (char)0xDFFF, false)), fields());
        row(4, fields("entry", "translate", "arguments", new String[]{"(char)0xD800", "'A'", "true"}),
                fields("holds", SurrogateUnits.translate((char)0xD800, 'A', true)), fields());
        row(5, fields("entry", "translate", "arguments", new String[]{"(char)0xD800", "'A'", "false"}),
                fields("holds", SurrogateUnits.translate((char)0xD800, 'A', false)), fields());
        row(6, fields("entry", "translate", "arguments", new String[]{"'A'", "(char)0xDC00", "true"}),
                fields("holds", SurrogateUnits.translate('A', (char)0xDC00, true)), fields());
        row(7, fields("entry", "translate", "arguments", new String[]{"'A'", "(char)0xDC00", "false"}),
                fields("holds", SurrogateUnits.translate('A', (char)0xDC00, false)), fields());
        row(8, fields("entry", "removeEvery", "arguments", new String[]{"'A'", "'B'"}),
                fields("holds", SurrogateUnits.removeEvery('A', 'B')), fields());
        row(9, fields("entry", "removeEvery", "arguments", new String[]{"(char)0xDBFF", "(char)0xDFFF"}),
                fields("holds", SurrogateUnits.removeEvery((char)0xDBFF, (char)0xDFFF)), fields());
    }
}
