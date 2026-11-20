package csvgrid;

import java.io.IOException;
import java.io.StringReader;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;

public final class Projection {
    static int limit(int digit) { return digit == 0 ? 1 : digit == 1 ? 2 : 10; }
    static CSVFormat format(int digit) { return CSVFormat.DEFAULT.builder().setMaxRows(limit(digit)).get(); }
    static int count(CSVFormat format) throws IOException {
        try (CSVParser reader = format.parse(new StringReader("a\nb\nc\n"))) {
            return reader.getRecords().size();
        }
    }
    public static int equal(int code) {
        return format(code / 3).equals(format(code % 3)) == (code / 3 == code % 3) ? 1 : 0;
    }
    public static int hashContract(int code) {
        CSVFormat a = format(code / 3), b = format(code % 3);
        return !a.equals(b) || a.hashCode() == b.hashCode() ? 1 : 0;
    }
    public static int rows(int code) throws IOException {
        int left = code / 3, right = code % 3;
        return count(format(left)) == Math.min(limit(left), 3) && count(format(right)) == Math.min(limit(right), 3) ? 1 : 0;
    }
}
