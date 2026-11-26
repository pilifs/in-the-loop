import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.parquet.column.ColumnDescriptor;
import org.apache.parquet.column.page.DictionaryPageReadStore;
import org.apache.parquet.example.data.Group;
import org.apache.parquet.example.data.simple.SimpleGroupFactory;
import org.apache.parquet.hadoop.*;
import org.apache.parquet.hadoop.example.*;
import org.apache.parquet.hadoop.util.HadoopInputFile;
import org.apache.parquet.schema.*;
import org.apache.parquet.schema.PrimitiveType.PrimitiveTypeName;

import java.util.*;

public class PublicCaller {
    static Set<String> dictionary(DictionaryPageReadStore store, ColumnDescriptor column)
            throws Exception {
        var page = store.readDictionaryPage(column);
        var d = page.getEncoding().initDictionary(column, page);
        Set<String> values = new TreeSet<>();
        for (int i = 0; i <= d.getMaxId(); i++) values.add(d.decodeToBinary(i).toStringUsingUTF8());
        return values;
    }

    public static String observe(String[] a) throws Exception {
        boolean vary = a[0].equals("challenge");
        String top = a[0].equals("control") ? "plain" : "a.b";
        var schema =
                Types.buildMessage()
                        .required(PrimitiveTypeName.BINARY)
                        .as(LogicalTypeAnnotation.stringType())
                        .named(top)
                        .requiredGroup()
                        .required(PrimitiveTypeName.BINARY)
                        .as(LogicalTypeAnnotation.stringType())
                        .named("b")
                        .named("a")
                        .named("msg");
        var conf = new Configuration();
        GroupWriteSupport.setSchema(schema, conf);
        var factory = new SimpleGroupFactory(schema);
        var path =
                new Path(
                        java.nio.file.Path.of(System.getProperty("java.io.tmpdir"), "rows.parquet")
                                .toUri());
        try (var writer =
                ExampleParquetWriter.builder(path)
                        .withConf(conf)
                        .withDictionaryEncoding(true)
                        .build()) {
            for (int i = 0; i < 100; i++) {
                String suffix = i % 2 == 0 ? "one" : "two";
                Group g = factory.newGroup().append(top, suffix);
                g.addGroup("a").append("b", (vary ? "new-" : "nested-") + suffix);
                writer.write(g);
            }
        }
        try (var reader = ParquetFileReader.open(HadoopInputFile.fromPath(path, conf))) {
            var store = reader.getNextDictionaryReader();
            var flat = schema.getColumnDescription(new String[] {top});
            var nested = schema.getColumnDescription(new String[] {"a", "b"});
            return (vary ? dictionary(store, nested) + "/" : "")
                    + dictionary(store, flat)
                    + "/"
                    + dictionary(store, nested);
        }
    }
}
