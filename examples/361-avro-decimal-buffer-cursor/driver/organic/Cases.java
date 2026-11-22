package organic;

import java.math.BigDecimal;
import java.nio.ByteBuffer;
import org.apache.avro.Conversions.DecimalConversion;
import org.apache.avro.LogicalType;
import org.apache.avro.LogicalTypes;
import org.apache.avro.Schema;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static int[] value(BigDecimal d) {
        return new int[]{d.unscaledValue().intValueExact(), d.scale()};
    }

    public static void main(String[] args) {
        for (int code = 0; code < 12; code++) {
            int start = DecimalWindow.start(code);
            int width = DecimalWindow.width(code);
            int scale = DecimalWindow.scale(code);
            ByteBuffer caller = ByteBuffer.wrap(DecimalWindow.bytes(), start, width);
            LogicalType type = LogicalTypes.decimal(9, scale);
            Schema schema = Schema.create(Schema.Type.BYTES);
            DecimalConversion conversion = new DecimalConversion();
            int[] first = value(conversion.fromBytes(caller, schema, type));
            int[] cursor = {caller.position(), caller.limit()};
            Object second;
            try {
                second = value(conversion.fromBytes(caller, schema, type));
            } catch (NumberFormatException exhausted) {
                second = exhausted.getClass().getName();
            }
            row(code, fields("start", start, "width", width, "scale", scale),
                fields("cursor", cursor, "decimals", new Object[]{first, second}),
                fields("cursor", DecimalWindow.cursor(code), "decimals", DecimalWindow.decimals(code)));
        }
    }
}
