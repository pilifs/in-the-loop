import org.apache.avro.*;

import java.math.*;
import java.nio.*;

public class PublicCaller {
    static String parts(BigDecimal b) {
        return b.unscaledValue() + "@" + b.scale();
    }

    static class Variable {
        static String run(boolean slice) {
            var encoder = new Conversions.BigDecimalConversion();
            var decoder = new Conversions.BigDecimalConversion();
            var schema = encoder.getRecommendedSchema();
            var type = LogicalTypes.bigDecimal();
            var a = encoder.toBytes(new BigDecimal(slice ? "7" : "12.3"), schema, type);
            var b = encoder.toBytes(new BigDecimal("12.30"), schema, type);
            if (!slice)
                return parts(decoder.fromBytes(a, schema, type))
                        + "/"
                        + parts(decoder.fromBytes(b, schema, type));
            int offset = a.remaining();
            var joined = ByteBuffer.allocate(offset + b.remaining());
            joined.put(a).put(b).flip().position(offset);
            var view = joined.slice();
            byte[] copy = new byte[view.remaining()];
            view.duplicate().get(copy);
            return parts(decoder.fromBytes(ByteBuffer.wrap(copy), schema, type))
                    + "/"
                    + parts(decoder.fromBytes(view, schema, type));
        }
    }

    public static String observe(String[] a) {
        Schema physical = Schema.create(Schema.Type.BYTES);
        if (!a[0].equals("control")) return Variable.run(a[0].equals("challenge"));
        var type = LogicalTypes.decimal(6, 2);
        var schema = type.addToSchema(physical);
        var converter = new Conversions.DecimalConversion();
        var bytes = converter.toBytes(new BigDecimal("-12.30"), schema, type);
        return parts(new Conversions.DecimalConversion().fromBytes(bytes, schema, type));
    }
}
