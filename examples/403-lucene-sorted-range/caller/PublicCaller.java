import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.lucene.document.*;
import org.apache.lucene.index.*;
import org.apache.lucene.search.*;
import org.apache.lucene.store.*;

public class PublicCaller {
    static String hits(IndexSearcher searcher, Query query) throws Exception {
        List<String> ids = new ArrayList<>();
        for (ScoreDoc hit : searcher.search(query, 10).scoreDocs)
            ids.add(searcher.storedFields().document(hit.doc).get("id"));
        Collections.sort(ids);
        return ids.toString();
    }

    public static String observe(String[] args) throws Exception {
        boolean reverse = args[0].equals("reverse");
        var sort = new SortedNumericSortField("dv", SortField.Type.INT, reverse);
        if (!args[0].equals("default")) sort.setMissingValue(reverse ? Integer.MIN_VALUE : 7);
        try (Directory dir = new ByteBuffersDirectory()) {
            try (var writer = new IndexWriter(dir, new IndexWriterConfig().setIndexSort(new Sort(sort)))) {
                for (int i = 0; i < 4; i++) {
                    Document doc = new Document();
                    doc.add(new StoredField("id", String.valueOf((char) ('A' + i))));
                    if (i < 3) {
                        int value = new int[]{3, 7, 9}[i];
                        doc.add(new SortedNumericDocValuesField("dv", value));
                        doc.add(new IntPoint("idx", value));
                    }
                    writer.addDocument(doc);
                }
            }
            try (var reader = DirectoryReader.open(dir)) {
                if (reader.leaves().size() != 1 || reader.hasDeletions()) throw new AssertionError("segment");
                IndexSearcher s = new IndexSearcher(reader);
                Query q = new IndexSortSortedNumericDocValuesRangeQuery("dv", 7, 8,
                        SortedNumericDocValuesField.newSlowRangeQuery("dv", 7, 8));
                Query point = IntPoint.newRangeQuery("idx", 7, 8);
                String ids, count;
                try { ids = hits(s, q); } catch (ClassCastException e) { ids = e.getClass().getSimpleName(); }
                try { count = Integer.toString(s.count(q)); } catch (ClassCastException e) { count = e.getClass().getSimpleName(); }
                return "hits=" + ids + ",count=" + count + "; points=" + hits(s, point) + "/" + s.count(point);
            }
        }
    }
}
