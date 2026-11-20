package csvgrid;

import java.io.StringReader;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class CsvCases {
    private static int read(CSVFormat format) throws Exception {
        int count = 0;
        try (CSVParser parser = format.parse(new StringReader("a\nb\nc\n"))) {
            for (Object row : parser) count++;
        }
        return count;
    }
    public static void main(String[] args) throws Exception {
        int code = 0;
        for (int left : new int[]{1, 2, 10}) {
            for (int right : new int[]{1, 2, 10}) {
                CSVFormat a = CSVFormat.DEFAULT.builder().setMaxRows(left).get();
                CSVFormat b = CSVFormat.DEFAULT.builder().setMaxRows(right).get();
                boolean equal = a.equals(b);
                Grid.row(code, new int[]{left, right},
                        fields("equal", equal, "hashContract", !equal || a.hashCode() == b.hashCode(),
                               "rows", new int[]{read(a), read(b)}),
                        fields("equal", Projection.equal(code), "hashContract", Projection.hashContract(code),
                               "rows", Projection.rows(code)));
                code++;
            }
        }
    }
}
