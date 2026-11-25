import java.io.*;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.apache.commons.csv.*;

public class PublicCaller {
    static List<CSVRecord> read(byte[] bytes, int start, CSVFormat format) throws IOException {
        try (var p = CSVParser.builder().setFormat(format).setTrackBytes(true)
                .setInputStream(new ByteArrayInputStream(bytes, start, bytes.length - start))
                .setCharset(StandardCharsets.UTF_8).get()) {
            List<CSVRecord> records = new ArrayList<>();
            for (var record : p) records.add(record);
            return records;
        }
    }

    static String describe(List<CSVRecord> rows) {
        var text = new StringJoiner("; ");
        for (var row : rows) {
            var fields = new ArrayList<String>();
            for (int i = 0; i < row.size(); i++) fields.add(row.get(i));
            text.add(fields + "@" + row.getBytePosition());
        }
        return text.toString();
    }

    public static String observe(String[] args) throws Exception {
        String delimiter = args[0].equals("ascii") ? "x" : "x😀";
        String end = args[0].equals("crlf") ? "\r\n" : "\n";
        var format = CSVFormat.DEFAULT.builder().setDelimiter(delimiter).get();
        byte[] bytes = ("a" + delimiter + "b" + end + "c" + delimiter + "d" + end).getBytes(StandardCharsets.UTF_8);
        try {
            var rows = read(bytes, 0, format);
            String result = describe(rows);
            if (args[0].equals("crlf"))
                result += "; suffix=" + describe(read(bytes, Math.toIntExact(rows.get(1).getBytePosition()), format));
            return result;
        } catch (UncheckedIOException e) {
            return e.getClass().getSimpleName() + " caused by " + e.getCause().getClass().getSimpleName()
                    + " CharacterCodingException=" + (e.getCause() instanceof CharacterCodingException);
        }
    }
}
