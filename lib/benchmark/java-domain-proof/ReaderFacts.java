package campaign;
import java.io.EOFException;
import java.io.IOException;
import java.util.Arrays;
import org.apache.avro.Schema;
import org.apache.avro.generic.GenericData;
import org.apache.avro.io.BinaryDecoder;
import org.apache.avro.io.DecoderFactory;

/** Public producer claims shared by the enum reader and the fast reader's integer marker. */
public final class ReaderFacts {
    public static int oneByte(int wire) throws IOException {
        byte[] bytes = {(byte) wire};
        BinaryDecoder decoder = DecoderFactory.get().binaryDecoder(bytes, null);
        int actual = decoder.readInt();
        int magnitude = wire / 2;
        int expected = (wire & 1) == 0 ? magnitude : -magnitude - 1;
        if (actual != expected) return 0;
        try {
            decoder.readInt();
            return 0;
        } catch (EOFException expectedEnd) {
            return 1;
        }
    }

    public static int configuredByte(int wire) throws IOException {
        System.clearProperty("org.apache.avro.limits.bytes.maxLength");
        return oneByte(wire);
    }

    public static int fields(int code) {
        Schema type = Schema.create(Schema.Type.INT);
        Schema.Field marker = new Schema.Field("marker", type);
        Schema.Field tag = new Schema.Field("tag", type);
        boolean reverse = (code & 1) != 0;
        Schema schema = Schema.createRecord("RecordA", null, null, false,
            reverse ? Arrays.asList(tag, marker) : Arrays.asList(marker, tag));
        GenericData.Record record = new GenericData.Record(schema);
        Integer m = Integer.valueOf(code - 2), t = Integer.valueOf(40 + code);
        record.put(reverse ? 1 : 0, m);
        record.put(reverse ? 0 : 1, t);
        return record.get("marker") == m && record.get("tag") == t ? 1 : 0;
    }
}
