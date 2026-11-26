import org.apache.commons.csv.*;

import java.io.*;
import java.util.*;

public class PublicCaller {
    public static String observe(String[] a) throws Exception {
        List<List<String>> rows =
                switch (a[0]) {
                    case "control" -> List.of(List.of("a", "b"), List.of("c", "d"));
                    case "challenge" -> List.of(List.of("", "x"), List.of("", "comma,\"quote"));
                    default -> List.of(List.of("a", "b"), List.of("", "x"));
                };
        StringWriter text = new StringWriter();
        try (var writer = new CSVPrinter(text, CSVFormat.MONGODB_CSV)) {
            for (var row : rows) writer.printRecord(row);
        }
        List<List<String>> read = new ArrayList<>();
        try (var parser = CSVParser.parse(text.toString(), CSVFormat.MONGODB_CSV)) {
            for (var row : parser) {
                List<String> fields = new ArrayList<>();
                for (int i = 0; i < row.size(); i++) fields.add(row.get(i));
                read.add(fields);
            }
        }
        return read.toString();
    }
}
