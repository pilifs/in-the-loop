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
        try (CSVParser parser = DelimitedFields.parse(new StringReader(text), delimiter)) {
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
            String d = DelimitedFields.delimiter(code), s = DelimitedFields.source(code,d);
            String cd = DelimitedFields.controlDelimiter(code), cs = DelimitedFields.controlSource(code);
            row(code, fields("delimiter", d, "source", s, "controlDelimiter", cd, "controlSource", cs),
                fields("fields", rows(s,d),
                       "prefixes", rows(cs,cd)),
                fields("fields", DelimitedFields.fields(code), "prefixes", DelimitedFields.prefixes(code)));
        }
    }
}
