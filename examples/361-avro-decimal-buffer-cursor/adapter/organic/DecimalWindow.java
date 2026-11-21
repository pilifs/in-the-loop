package organic;

import java.math.BigDecimal;
import java.nio.ByteBuffer;
import org.apache.avro.Conversions.DecimalConversion;
import org.apache.avro.LogicalType;
import org.apache.avro.LogicalTypes;
import org.apache.avro.Schema;

public final class DecimalWindow {
    static int start(int code) { return 1 + code / 4; }
    static int width(int code) { return 1 + (code / 2) % 2; }
    static int scale(int code) { return 2 * (code % 2); }
    static byte[] bytes() { return new byte[]{99, -128, 1, 127, -1, 42}; }

    static ByteBuffer buffer(int code) {
        return ByteBuffer.wrap(bytes(), start(code), width(code));
    }

    public static int cursor(int code) {
        LogicalType decimal = LogicalTypes.decimal(9, scale(code));
        Schema schema = Schema.create(Schema.Type.BYTES);
        ByteBuffer original = buffer(code);
        new DecimalConversion().fromBytes(original, schema, decimal);
        return original.position() == start(code) && original.limit() == start(code) + width(code) ? 1 : 0;
    }

    public static int decimals(int code) {
        LogicalType decimal = LogicalTypes.decimal(9, scale(code));
        Schema schema = Schema.create(Schema.Type.BYTES);
        ByteBuffer original = buffer(code);
        DecimalConversion conversion = new DecimalConversion();
        byte[] backing = bytes();
        int first = start(code);
        int expected = backing[first];
        if (width(code) == 2) expected = expected * 256 + (backing[first + 1] & 255);
        BigDecimal a = conversion.fromBytes(original, schema, decimal);
        try {
            BigDecimal b = conversion.fromBytes(original, schema, decimal);
            return a.scale() == scale(code) && b.scale() == scale(code)
                && a.unscaledValue().intValueExact() == expected && b.unscaledValue().intValueExact() == expected ? 1 : 0;
        } catch (NumberFormatException emptyWindow) {
            return 0;
        }
    }
}
