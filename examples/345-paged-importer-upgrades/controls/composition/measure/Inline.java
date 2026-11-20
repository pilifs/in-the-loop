package measure;

import importer.PageImporter;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class Inline {
    public static void main(String[] args) throws Exception {
        BufferedReader cases = java.nio.file.Files.newBufferedReader(java.nio.file.Path.of(args[0]), StandardCharsets.UTF_8);
        String row;
        while ((row = cases.readLine()) != null) {
            String[] in = row.split("\t", -1);
            byte[] supplied = HexFormat.of().parseHex(in[1]);
            boolean narrow = in[2].equals("1"), preview = in[3].equals("1");
            int start = Integer.parseInt(in[4]), cap = Integer.parseInt(in[5]);
            byte[] bytes = PageImporter.remaining(supplied, narrow, preview);
            List<Object> page = new ArrayList<>();
            for (PageImporter.Row record : PageImporter.page(supplied, narrow, preview, start, cap))
                page.add(List.of(record.number(), record.fields()));
            Grid.row(Integer.parseInt(in[0]), List.of(in[1], narrow, preview, start, cap),
                    fields("bytes", HexFormat.of().formatHex(bytes), "count", page.size(), "page", page), fields());
        }
    }
}
