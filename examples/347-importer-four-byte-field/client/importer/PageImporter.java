package importer;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;
import org.apache.commons.io.ByteOrderMark;
import org.apache.commons.io.input.BOMInputStream;

/** The application is compiled once against CSV's declared dependencies. */
public final class PageImporter {
    private PageImporter() {}

    public record Row(long number, List<String> fields) {}

    private static InputStream open(byte[] source, boolean oneByte, boolean preview) throws IOException {
        ByteArrayInputStream delegate = new ByteArrayInputStream(source) {
            @Override public synchronized int read(byte[] buffer, int offset, int length) {
                return super.read(buffer, offset, oneByte ? Math.min(1, length) : length);
            }
        };
        BOMInputStream stream = BOMInputStream.builder().setInputStream(delegate)
                .setByteOrderMarks(ByteOrderMark.UTF_8).setInclude(false).get();
        if (preview) {
            stream.read();
            stream.reset();
        }
        return stream;
    }

    public static byte[] remaining(byte[] source, boolean oneByte, boolean preview) throws IOException {
        try (InputStream input = open(source, oneByte, preview)) {
            return input.readAllBytes();
        }
    }

    public static List<Row> page(byte[] source, boolean oneByte, boolean preview, int start, int cap)
            throws IOException {
        CSVFormat format = CSVFormat.DEFAULT.builder().setMaxRows(cap).get();
        try (InputStreamReader reader = new InputStreamReader(open(source, oneByte, preview), StandardCharsets.UTF_8);
             CSVParser parser = CSVParser.builder().setReader(reader).setFormat(format).setRecordNumber(start).get()) {
            List<Row> result = new ArrayList<>();
            for (CSVRecord record : parser) {
                result.add(new Row(record.getRecordNumber(), record.toList()));
            }
            return result;
        }
    }
}
