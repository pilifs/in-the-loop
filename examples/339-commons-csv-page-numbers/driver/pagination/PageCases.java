package pagination;

import java.io.StringReader;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;
import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class PageCases {
    public static void main(String[] args) throws Exception {
        int code = 0;
        for (int rows = 1; rows <= 3; rows++) {
            StringBuilder doc = new StringBuilder();
            for (int i = 1; i <= rows; i++) doc.append("r,").append(i).append('\n');
            for (int start = 1; start <= 2; start++) {
                for (int cap = 1; cap <= 2; cap++) {
                    for (boolean twice : new boolean[]{false, true}) {
                        CSVFormat format = CSVFormat.DEFAULT.builder().setMaxRows(cap).get();
                        try (CSVParser parser = CSVParser.builder().setReader(new StringReader(doc.toString()))
                                .setFormat(format).setRecordNumber(start).get()) {
                            List<Long> labels = new ArrayList<>();
                            List<List<String>> values = new ArrayList<>();
                            Iterator<CSVRecord> iterator = parser.iterator();
                            while (iterator.hasNext()) {
                                if (twice && !iterator.hasNext()) throw new AssertionError("prefetched record disappeared");
                                CSVRecord record = iterator.next();
                                labels.add(record.getRecordNumber());
                                values.add(record.toList());
                            }
                            Grid.row(code, fields("rows", rows, "start", start, "cap", cap, "twice", twice),
                                    fields("count", labels.size(), "labels", labels, "fields", values),
                                    fields("count", Projection.count(code), "labels", Projection.labels(code),
                                            "fields", Projection.fields(code)));
                            code++;
                        }
                    }
                }
            }
        }
    }
}
