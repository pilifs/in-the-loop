package importer;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class ImportCases {
    public static void main(String[] args) throws Exception {
        String[] docs = {"a,b\nc,d\n", "x,y\n", "z,1\nz,2\nz,3\n"};
        int code = 0;
        for (String doc : docs) {
            for (boolean bom : new boolean[]{false, true}) {
                for (boolean oneByte : new boolean[]{false, true}) {
                    for (boolean preview : new boolean[]{false, true}) {
                        for (int start = 1; start <= 2; start++) {
                            for (int cap = 1; cap <= 2; cap++) {
                                byte[] source = ((bom ? "\uFEFF" : "") + doc).getBytes(StandardCharsets.UTF_8);
                                byte[] remaining = PageImporter.remaining(source, oneByte, preview);
                                int[] unsigned = new int[remaining.length];
                                for (int i = 0; i < remaining.length; i++) unsigned[i] = remaining[i] & 255;
                                List<PageImporter.Row> rows = PageImporter.page(source, oneByte, preview, start, cap);
                                List<Object> page = new ArrayList<>();
                                for (PageImporter.Row row : rows) page.add(List.of(row.number(), row.fields()));
                                Grid.row(code, fields("doc", doc, "bom", bom, "oneByte", oneByte,
                                                "preview", preview, "start", start, "cap", cap),
                                        fields("bytes", unsigned, "count", rows.size(), "page", page),
                                        fields("bytes", Projection.bytes(code), "count", Projection.count(code),
                                                "page", Projection.page(code)));
                                code++;
                            }
                        }
                    }
                }
            }
        }
    }
}
