package campaign;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import org.apache.avro.Schema;
import org.apache.avro.generic.GenericData;
import org.apache.avro.generic.GenericDatumReader;
import org.apache.avro.generic.GenericRecord;
import org.apache.avro.io.Decoder;
import org.apache.avro.io.DecoderFactory;

public final class DefaultReader {
    static Schema record(List<Schema.Field> fields) {
        return Schema.createRecord("RecordA", null, null, false, fields);
    }
    static Schema schema(int code, boolean reader, boolean union, boolean required) {
        List<Schema.Field> fields = new ArrayList<>();
        if (code != 0) fields.add(new Schema.Field("marker", Schema.create(Schema.Type.INT)));
        if (reader) {
            Schema element = Schema.createRecord("Element", null, null, false,
                Collections.singletonList(new Schema.Field("value", Schema.create(Schema.Type.INT))));
            Schema type = Schema.createArray(element);
            if (union) type = Schema.createUnion(Arrays.asList(type, Schema.create(Schema.Type.NULL)));
            fields.add(required ? new Schema.Field("fieldA", type)
                                : new Schema.Field("fieldA", type, null, Collections.emptyList()));
        }
        return record(fields);
    }

    static int marker(int code) { return code - 2; }

    static GenericRecord read(int code, boolean union, boolean required, boolean fast, boolean json) throws IOException {
        Schema writer = schema(code, false, false, false);
        Schema reader = schema(code, true, union, required);
        GenericData data = new GenericData();
        data.setFastReaderEnabled(fast);
        GenericDatumReader<GenericRecord> datum = new GenericDatumReader<>(null, null, data);
        datum.setExpected(reader);
        datum.setSchema(writer);
        Decoder decoder;
        if (json) {
            String text = code == 0 ? "{}" : "{\"marker\":" + marker(code) + "}";
            decoder = DecoderFactory.get().jsonDecoder(writer, text);
        } else {
            int value = marker(code);
            byte[] wire = code == 0 ? new byte[0] : new byte[]{(byte) ((value << 1) ^ (value >> 31))};
            decoder = DecoderFactory.get().binaryDecoder(wire, null);
        }
        return datum.read(null, decoder);
    }

    static int check(int code, boolean union) throws IOException {
        try {
            GenericRecord result = read(code, union, false, true, false);
            Object array = result.get("fieldA");
            if (!(array instanceof List) || ((List<?>) array).size() != 0) return 0;
            if (code == 0) return 1;
            Object actual = result.get("marker");
            return actual instanceof Integer && ((Integer) actual).intValue() == marker(code) ? 1 : 0;
        } catch (org.apache.avro.AvroRuntimeException failure) {
            return 0;
        }
    }

    public static int union(int code) throws IOException { return check(code, true); }
    public static int direct(int code) throws IOException { return check(code, false); }
}
