package pagination;

import java.io.IOException;
import java.io.StringReader;
import java.util.Iterator;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;

public final class Projection {
    private static int check(int code, int observer) throws IOException {
        int rows = 1 + code / 8;
        int start = 1 + ((code >>> 2) & 1);
        int cap = 1 + ((code >>> 1) & 1);
        String doc = rows == 1 ? "r,1\n" : rows == 2 ? "r,1\nr,2\n" : "r,1\nr,2\nr,3\n";
        CSVFormat format = CSVFormat.DEFAULT.builder().setMaxRows(cap).get();
        try (CSVParser parser = CSVParser.builder().setReader(new StringReader(doc)).setFormat(format)
                .setRecordNumber(start).get()) {
            Iterator<CSVRecord> iterator = parser.iterator();
            int count = 0;
            while (iterator.hasNext()) {
                if ((code & 1) != 0 && !iterator.hasNext()) return 0;
                CSVRecord record = iterator.next();
                if (observer == 1 && record.getRecordNumber() != start + count) return 0;
                if (observer == 2 && (record.size() != 2 || !"r".equals(record.get(0))
                        || !(count == 0 ? "1" : "2").equals(record.get(1)))) return 0;
                count++;
            }
            return count == Math.min(rows, cap) ? 1 : 0;
        }
    }

    public static int count(int code) throws IOException { return check(code, 0); }
    public static int labels(int code) throws IOException { return check(code, 1); }
    public static int fields(int code) throws IOException { return check(code, 2); }
}
