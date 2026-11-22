package campaign;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.List;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static List<List<String>> rows(String text, String delimiter) throws Exception {
        List<List<String>> rows = new ArrayList<>();
        try (CSVParser parser = CappedFields.parse(new CappedReader(text, 1), delimiter)) {
            for (CSVRecord record : parser) {
                List<String> fields = new ArrayList<>();
                for (int i = 0; i < record.size(); i++) fields.add(record.get(i));
                rows.add(fields);
            }
        }
        return rows;
    }
    public static void main(String[] args) throws Exception {
        for (int code=0; code<14; code++) {
            String d = CappedFields.delimiter(code), s = CappedFields.source(code,d);
            String cd = CappedFields.controlDelimiter(code), cs = CappedFields.controlSource(code);
            row(code, fields("delimiter", d, "source", s, "controlDelimiter", cd, "controlSource", cs),
                fields("fields", rows(s,d),
                       "prefixes", rows(cs,cd)),
                fields("fields", CappedFields.fields(code), "prefixes", CappedFields.prefixes(code)));
        }
    }
}
