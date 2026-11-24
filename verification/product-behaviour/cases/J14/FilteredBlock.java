import java.util.ArrayList;
import java.util.List;
import org.apache.lucene.document.*;
import org.apache.lucene.index.*;
import org.apache.lucene.search.*;
import org.apache.lucene.search.join.*;
import org.apache.lucene.store.*;
import org.apache.lucene.util.BytesRef;

public class FilteredBlock {
    private static Document child(String value, boolean selected) {
        Document doc = new Document();
        doc.add(new StringField("kind","child",Field.Store.NO));
        if (selected) doc.add(new StringField("selected","yes",Field.Store.NO));
        if (value != null) doc.add(new SortedDocValuesField("sort",new BytesRef(value)));
        return doc;
    }
    public static void main(String[] args) throws Exception {
        String extra = args[0];
        try (Directory dir = new ByteBuffersDirectory()) {
            try (IndexWriter writer = new IndexWriter(dir,new IndexWriterConfig())) {
                List<Document> block = new ArrayList<>();
                block.add(child("30",true));
                if (!extra.equals("absent")) block.add(child(extra.equals("valued") ? "05" : null,false));
                Document parent = new Document();
                parent.add(new StringField("kind","parent",Field.Store.NO));
                block.add(parent);
                writer.addDocuments(block);
            }
            try (DirectoryReader reader = DirectoryReader.open(dir)) {
                IndexSearcher search = new IndexSearcher(reader);
                var parents = new TermQuery(new Term("kind","parent"));
                var selected = new TermQuery(new Term("selected","yes"));
                TopFieldDocs results = search.search(parents,2,new Sort(new ToParentBlockJoinSortField("sort",SortField.Type.STRING,false,
                        new QueryBitSetProducer(parents),new QueryBitSetProducer(selected))));
                if (results.totalHits.value() != 1 || search.count(selected) != 1) throw new AssertionError("selection differs");
                Object key = ((FieldDoc)results.scoreDocs[0]).fields[0];
                System.out.println("block=" + search.count(new TermQuery(new Term("kind","child")))
                        + " selected=1 sort=" + (key == null ? "null" : ((BytesRef)key).utf8ToString()));
            }
        }
    }
}
