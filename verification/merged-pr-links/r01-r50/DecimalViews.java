import org.apache.avro.Conversions;
import org.apache.avro.LogicalTypes;
import org.apache.avro.Schema;

import java.math.BigDecimal;
import java.nio.ByteBuffer;

public class DecimalViews {
    public static String observe(String[] args) {
        return VariableDecimal.read(args[0], Schema.create(Schema.Type.BYTES));
    }

    // The physical bytes schema also exists on versions before the logical type.
    private static class VariableDecimal {
        static String read(String mode, Schema physical) {
            var conversion = new Conversions.BigDecimalConversion();
            var logical = LogicalTypes.bigDecimal();
            var schema = logical.addToSchema(physical);
            ByteBuffer encoded = conversion.toBytes(new BigDecimal("12.30"), schema, logical);
            ByteBuffer view =
                    switch (mode) {
                        case "read-only" -> encoded.asReadOnlyBuffer();
                        case "direct" ->
                                ByteBuffer.allocateDirect(encoded.remaining())
                                        .put(encoded.duplicate())
                                        .flip();
                        case "heap" -> encoded;
                        default -> throw new IllegalArgumentException(mode);
                    };
            int start = view.position();
            BigDecimal result =
                    new Conversions.BigDecimalConversion().fromBytes(view, schema, logical);
            return result.unscaledValue()
                    + "@"
                    + result.scale()
                    + ", cursor="
                    + (view.position() - start);
        }
    }
}
