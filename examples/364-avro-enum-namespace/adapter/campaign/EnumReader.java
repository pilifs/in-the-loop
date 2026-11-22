package campaign;
import java.io.IOException;
import java.util.Arrays;
import java.util.Collections;
import org.apache.avro.AvroTypeException;
import org.apache.avro.Schema;
import org.apache.avro.generic.GenericDatumReader;
import org.apache.avro.generic.GenericRecord;
import org.apache.avro.io.DecoderFactory;

public final class EnumReader {
    static Schema record(String name, String namespace, boolean reversed) {
        Schema e = Schema.createEnum(name, null, namespace,
                reversed ? Arrays.asList("B", "A") : Arrays.asList("A", "B"));
        return Schema.createRecord("MyRecord", null, null, false,
                Collections.singletonList(new Schema.Field("field", e)));
    }

    static String read(int code, String name, String namespace) throws IOException {
        Schema writer = record("E", "writer", false);
        Schema reader = record(name, namespace, (code & 2) != 0);
        GenericDatumReader<GenericRecord> datum = new GenericDatumReader<>(writer, reader);
        byte[] bytes = {(byte) ((code & 1) * 2)};
        try {
            GenericRecord result = datum.read(null, DecoderFactory.get().binaryDecoder(bytes, null));
            return result.get("field").toString();
        } catch (AvroTypeException failure) {
            return failure.getClass().getName();
        }
    }

    public static int renamed(int code) throws IOException {
        return ((code & 1) == 0 ? "A" : "B").equals(read(code, "E", "reader")) ? 1 : 0;
    }

    public static int preserved(int code) throws IOException {
        String symbol = read(code, "E", "writer");
        String different = read(code, "Other", "reader");
        return ((code & 1) == 0 ? "A" : "B").equals(symbol)
            && "org.apache.avro.AvroTypeException".equals(different) ? 1 : 0;
    }
}
