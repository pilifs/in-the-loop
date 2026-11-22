package campaign;

import java.io.IOException;
import java.io.Reader;
import java.io.StringReader;
import java.util.Iterator;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;

public final class CappedFields {
    static String delimiter(int code) {
        return code < 4 || code >= 12 ? "||" : code < 8 ? "|||" : "|~|";
    }
    static String[] shape(int code, String d) {
        if (code == 12) return new String[]{"a","b","c","d","","f"};
        if (code == 13) return new String[]{"a","b||c","d","","f"};
        return switch (code & 3) {
            case 0 -> new String[]{"a","b","c"};
            case 1 -> new String[]{"a","","b"};
            case 2 -> new String[]{"a","b"+d+"c","d"};
            default -> new String[]{"a","b",""};
        };
    }
    static String source(int code, String d) {
        if (code == 12) return "a||b||c||d||||f";
        if (code == 13) return "a||\"b||c\"||d||||f";
        return switch (code & 3) {
            case 0 -> "a"+d+"b"+d+"c";
            case 1 -> "a"+d+d+"b";
            case 2 -> "a"+d+"\"b"+d+"c\""+d+"d";
            default -> "a"+d+"b"+d;
        };
    }
    static String controlDelimiter(int code) {
        return switch (code % 7) {
            case 0 -> "||"; case 1, 2 -> "|||"; case 3, 4 -> "|~|"; default -> ",";
        };
    }
    static String controlSource(int code) {
        return switch (code % 7) {
            case 0, 1, 3 -> "a|b";
            case 2 -> "a||b";
            case 4 -> "a|~b";
            case 5 -> "a,b,";
            default -> "a,\"b,c\"";
        };
    }
    static String[] controlFields(int code) {
        return switch (code % 7) {
            case 5 -> new String[]{"a","b",""};
            case 6 -> new String[]{"a","b,c"};
            default -> new String[]{controlSource(code)};
        };
    }
    static CSVParser parse(Reader reader, String delimiter) throws IOException {
        CSVFormat format = CSVFormat.Builder.create().setDelimiter(delimiter).setQuote('"').build();
        return CSVParser.parse(reader, format);
    }
    static int matches(String source, String delimiter, String[] expected) throws IOException {
        try (CSVParser parser = parse(new CappedReader(source, 2), delimiter)) {
            Iterator<CSVRecord> rows = parser.iterator();
            if (!rows.hasNext()) return 0;
            CSVRecord first = rows.next();
            if (first.size() != expected.length) return 0;
            for (int i = 0; i < expected.length; i++) if (!expected[i].equals(first.get(i))) return 0;
            return rows.hasNext() ? 0 : 1;
        }
    }
    public static int fields(int code) throws IOException {
        String d = delimiter(code);
        return matches(source(code,d), d, shape(code,d));
    }
    public static int prefixes(int code) throws IOException {
        return matches(controlSource(code), controlDelimiter(code), controlFields(code));
    }
}
