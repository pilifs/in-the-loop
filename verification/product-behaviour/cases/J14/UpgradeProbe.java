import java.util.*;
import org.apache.lucene.document.*;
import org.apache.lucene.index.*;
import org.apache.lucene.search.*;
import org.apache.lucene.search.join.*;
import org.apache.lucene.store.*;
import org.apache.lucene.util.BytesRef;

public class UpgradeProbe {
    private static Document child(Integer value) {
        Document row = new Document();
        row.add(new StringField("kind","child", Field.Store.NO));
        if (value != null) {
            row.add(new StringField("present","yes",Field.Store.NO));
            row.add(new SortedDocValuesField("s",new BytesRef(value.toString())));
            row.add(new NumericDocValuesField("i",value));
        }
        return row;
    }
    private static Document parent(String id) {
        Document row = new Document();
        row.add(new StringField("kind","parent",Field.Store.NO)); row.add(new StoredField("id",id)); return row;
    }
    private static String hits(IndexSearcher search, Query parents, SortField sort) throws Exception {
        TopFieldDocs docs = search.search(parents, 10, new Sort(sort));
        StringJoiner rows = new StringJoiner(",");
        for (ScoreDoc doc : docs.scoreDocs) {
            Object key = ((FieldDoc)doc).fields[0];
            rows.add(search.storedFields().document(doc.doc).get("id") + ":" + (key instanceof BytesRef ? ((BytesRef)key).utf8ToString() : key));
        }
        return docs.totalHits.value() + "=" + rows;
    }
    public static String observe(String[] args) throws Exception {
        try (Directory dir = new ByteBuffersDirectory()) {
            try (IndexWriter writer = new IndexWriter(dir, new IndexWriterConfig())) {
                writer.addDocuments(List.of(child(30),child(args[0].equals("all") ? 35 : null),parent("A")));
                writer.addDocuments(List.of(child(20),child(40),parent("B")));
                writer.commit();
            }
            try (DirectoryReader reader = DirectoryReader.open(dir)) {
                IndexSearcher search = new IndexSearcher(reader);
                Query parents = new TermQuery(new Term("kind","parent"));
                if (search.count(new TermQuery(new Term("present","yes"))) != (args[0].equals("all") ? 4 : 3))
                    throw new AssertionError("unexpected number of children with a sort value");
                BitSetProducer p = new QueryBitSetProducer(parents);
                BitSetProducer children = new QueryBitSetProducer(new TermQuery(args[0].equals("filtered")
                        ? new Term("present","yes") : new Term("kind","child")));
                SortField field = new ToParentBlockJoinSortField("s", SortField.Type.STRING, args[1].equals("descending"), p, children);
                String result = hits(search, parents, field);
                if (args[0].equals("numeric")) {
                    try {
                        var ctor = ToParentBlockJoinSortField.class.getConstructor(String.class, SortField.Type.class,
                                boolean.class, Object.class, Object.class, BitSetProducer.class, BitSetProducer.class);
                        for (int replacement : new int[]{5,50}) {
                            SortField num = ctor.newInstance("i", SortField.Type.INT, false, 99, replacement, p, children);
                            result += "|" + hits(search, parents, num);
                        }
                    } catch (NoSuchMethodException e) { result += "|overload-absent"; }
                }
                return result;
            }
        }
    }
}
