package measure;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.StringReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;
import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

/** The parser consumes an exact post-decoding UTF-16 sequence. */
public final class CSVFact {
    public static void main(String[] args) throws Exception {
        BufferedReader cases = java.nio.file.Files.newBufferedReader(java.nio.file.Path.of(args[0]), StandardCharsets.UTF_8);
        String row;
        while ((row = cases.readLine()) != null) {
            String[] in = row.split("\t", -1);
            String decoded = new String(HexFormat.of().parseHex(in[1]), StandardCharsets.UTF_16BE);
            int start = Integer.parseInt(in[2]), cap = Integer.parseInt(in[3]);
            CSVFormat format = CSVFormat.DEFAULT.builder().setMaxRows(cap).get();
            List<Object> page = new ArrayList<>();
            try (CSVParser parser = CSVParser.builder().setReader(new StringReader(decoded)).setFormat(format)
                    .setRecordNumber(start).get()) {
                for (CSVRecord record : parser) page.add(List.of(record.getRecordNumber(), record.toList()));
            }
            Grid.row(Integer.parseInt(in[0]), List.of(in[1], start, cap), fields("count", page.size(), "page", page), fields());
        }
    }
}
