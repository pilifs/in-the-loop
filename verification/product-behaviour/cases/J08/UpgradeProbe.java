import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import org.apache.parquet.bytes.BytesInput;
import org.apache.parquet.bytes.HeapByteBufferAllocator;
import org.apache.parquet.column.ColumnDescriptor;
import org.apache.parquet.column.Encoding;
import org.apache.parquet.column.ParquetProperties.WriterVersion;
import org.apache.parquet.column.page.DataPageV1;
import org.apache.parquet.column.page.DictionaryPage;
import org.apache.parquet.column.values.ValuesReader;
import org.apache.parquet.column.values.dictionary.DictionaryValuesReader;
import org.apache.parquet.column.values.dictionary.DictionaryValuesWriter.PlainBinaryDictionaryValuesWriter;
import org.apache.parquet.column.values.fallback.FallbackValuesWriter;
import org.apache.parquet.column.values.plain.BinaryPlainValuesReader;
import org.apache.parquet.column.values.plain.PlainValuesWriter;
import org.apache.parquet.example.data.Group;
import org.apache.parquet.example.data.simple.SimpleGroupFactory;
import org.apache.parquet.example.data.simple.convert.GroupRecordConverter;
import org.apache.parquet.hadoop.ParquetFileReader;
import org.apache.parquet.hadoop.ParquetWriter;
import org.apache.parquet.hadoop.example.ExampleParquetWriter;
import org.apache.parquet.hadoop.metadata.CompressionCodecName;
import org.apache.parquet.io.ColumnIOFactory;
import org.apache.parquet.io.LocalInputFile;
import org.apache.parquet.io.LocalOutputFile;
import org.apache.parquet.io.api.Binary;
import org.apache.parquet.schema.MessageType;
import org.apache.parquet.schema.MessageTypeParser;

public class UpgradeProbe {
    private static final MessageType TYPE = MessageTypeParser.parseMessageType("message items { required binary v (UTF8); }");
    private static final int N = 1000;

    private static String value(int group, int i, boolean fallback) {
        return group == 0 ? "a" + (fallback ? i : i % 10) : "c" + (i % 10);
    }

    private static String dictionary(DictionaryPage page, ColumnDescriptor column, String prefix) throws Exception {
        if (page == null) return "none";
        var table = Encoding.PLAIN.initDictionary(column, page);
        for (int i = 0; i < page.getDictionarySize(); i++)
            if (!table.decodeToBinary(i).toStringUsingUTF8().equals(prefix + i))
                throw new AssertionError("unexpected dictionary value at " + i);
        return prefix + ":" + page.getDictionarySize();
    }

    public static String observe(String[] args) throws Exception {
        boolean fallback = args[1].equals("distinct");
        if (args[0].equals("page")) {
            var allocator = new HeapByteBufferAllocator();
            var initial = new PlainBinaryDictionaryValuesWriter(10000, Encoding.PLAIN_DICTIONARY, Encoding.PLAIN_DICTIONARY, allocator);
            try (var writer = FallbackValuesWriter.of(initial, new PlainValuesWriter(10000, 50000, allocator))) {
                String first = "fresh";
                if (!args[1].equals("fresh")) {
                    for (int i = 0; i < N; i++) writer.writeBytes(Binary.fromString(value(0, i, fallback)));
                    BytesInput.copy(writer.getBytes());
                    first = writer.getEncoding().name();
                    writer.reset();
                    writer.toDictPageAndClose();
                    writer.resetDictionary();
                }
                for (int i = 0; i < N; i++) writer.writeBytes(Binary.fromString(value(1, i, false)));
                BytesInput bytes = BytesInput.copy(writer.getBytes());
                Encoding encoding = writer.getEncoding();
                DictionaryPage page = writer.toDictPageAndClose();
                ColumnDescriptor column = TYPE.getColumns().get(0);
                ValuesReader reader = encoding.usesDictionary()
                        ? new DictionaryValuesReader(Encoding.PLAIN.initDictionary(column, page))
                        : new BinaryPlainValuesReader();
                reader.initFromPage(N, bytes.toInputStream());
                int matches = 0;
                String head = "", tail = "";
                for (int i = 0; i < N; i++) {
                    String actual = reader.readBytes().toStringUsingUTF8();
                    if (i == 0) head = actual;
                    tail = actual;
                    if (actual.equals(value(1, i, false))) matches++;
                }
                return first + "/" + encoding + "/" + dictionary(page, column, "c") + "/" + head + "/" + tail + "/" + matches;
            }
        }

        Path file = Path.of("groups.parquet");
        SimpleGroupFactory groups = new SimpleGroupFactory(TYPE);
        try (ParquetWriter<Group> writer = ExampleParquetWriter.builder(new LocalOutputFile(file)).withType(TYPE)
                .withWriterVersion(WriterVersion.PARQUET_1_0).withCompressionCodec(CompressionCodecName.UNCOMPRESSED)
                .withRowGroupRowCountLimit(N).withRowGroupSize(1L << 24).withPageSize(1 << 20)
                .withDictionaryPageSize(10000).withDictionaryEncoding(true).build()) {
            for (int group = 0; group < 2; group++)
                for (int i = 0; i < N; i++) writer.write(groups.newGroup().append("v", value(group, i, fallback)));
        }
        List<String> result = new ArrayList<>();
        // Use independent file handles for physical page metadata and the public record decoder.
        try (var pages = ParquetFileReader.open(new LocalInputFile(file));
             var records = ParquetFileReader.open(new LocalInputFile(file))) {
            for (int group = 0; group < 2; group++) {
                var pageStore = pages.readNextRowGroup();
                var recordStore = records.readNextRowGroup();
                if (pageStore.getRowCount() != N || recordStore.getRowCount() != N)
                    throw new AssertionError("unexpected row-group boundary");
                var col = TYPE.getColumns().get(0);
                var reader = pageStore.getPageReader(col);
                String table = dictionary(reader.readDictionaryPage(), col, group == 0 ? "a" : "c");
                DataPageV1 data = (DataPageV1) reader.readPage();
                if (data.getValueCount() != N || reader.readPage() != null) throw new AssertionError("unexpected page split");
                var rowReader = new ColumnIOFactory().getColumnIO(TYPE).getRecordReader(recordStore, new GroupRecordConverter(TYPE));
                int matches = 0;
                for (int i = 0; i < N; i++)
                    if (rowReader.read().getString("v", 0).equals(value(group, i, fallback))) matches++;
                result.add(data.getValueEncoding() + "/" + table + "/" + matches);
            }
            if (pages.readNextRowGroup() != null || records.readNextRowGroup() != null)
                throw new AssertionError("unexpected third row group");
        }
        return String.join("|", result);
    }
}
