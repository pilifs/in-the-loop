import org.apache.avro.*;
import org.apache.avro.generic.*;
import org.apache.avro.io.*;
import org.apache.avro.util.TimePeriod;

import java.io.*;
import java.nio.*;
import java.util.*;

public class PublicCaller {
    static byte[] encode(GenericData data, Schema schema, Object object) throws Exception {
        var out = new ByteArrayOutputStream();
        var e = EncoderFactory.get().binaryEncoder(out, null);
        data.createDatumWriter(schema).write(object, e);
        e.flush();
        return out.toByteArray();
    }

    static Object decode(GenericData data, Schema writer, Schema reader, byte[] bytes)
            throws Exception {
        return data.createDatumReader(writer, reader)
                .read(null, DecoderFactory.get().binaryDecoder(bytes, null));
    }

    static class Duration {
        static String fields(Object o) {
            var t = (TimePeriod) o;
            return t.getMonths() + "/" + t.getDays() + "/" + t.getMillis();
        }

        static String run(String arg, Schema raw, GenericData plain, byte[] first)
                throws Exception {
            var model = new GenericData();
            model.addLogicalTypeConversion(new Conversions.DurationConversion());
            var logical =
                    LogicalTypes.duration()
                            .addToSchema(Schema.createFixed("Duration", null, "caseR", 12));
            if (arg.equals("intent")) return fields(decode(model, raw, logical, first));
            List<String> results = new ArrayList<>();
            for (long ms : new long[] {4294967295L, 0L}) {
                byte[] b = encode(model, logical, TimePeriod.of(1, 2, ms));
                results.add(
                        HexFormat.of()
                                        .formatHex(
                                                ((GenericFixed) decode(plain, logical, raw, b))
                                                        .bytes())
                                + "/"
                                + fields(decode(model, logical, logical, b)));
            }
            return String.join(" / ", results);
        }
    }

    public static String observe(String[] a) throws Exception {
        var raw = Schema.createFixed("Duration", null, "caseR", 12);
        var plain = new GenericData();
        byte[] words =
                ByteBuffer.allocate(12)
                        .order(ByteOrder.LITTLE_ENDIAN)
                        .putInt(1)
                        .putInt(2)
                        .putInt(3)
                        .array();
        byte[] fixture = encode(plain, raw, new GenericData.Fixed(raw, words));
        if (a[0].equals("control"))
            return HexFormat.of()
                    .formatHex(((GenericFixed) decode(plain, raw, raw, fixture)).bytes());
        return Duration.run(a[0], raw, plain, fixture);
    }
}
