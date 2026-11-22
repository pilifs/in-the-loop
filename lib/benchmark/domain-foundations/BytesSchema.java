package foundation;

import com.fasterxml.jackson.core.JsonFactory;
import org.apache.avro.AvroRuntimeException;
import org.apache.avro.Schema;

public final class BytesSchema {
    public static boolean firstFactory() { return new JsonFactory().getCodec() == null; }

    public static boolean typed() {
        Schema first = Schema.create(Schema.Type.BYTES);
        Schema second = Schema.create(Schema.Type.BYTES);
        return first != second && first.getType() == Schema.Type.BYTES && second.getType() == first.getType();
    }

    public static boolean rejectsRecord() {
        try {
            Schema.create(Schema.Type.RECORD);
            return false;
        } catch (AvroRuntimeException expected) { return true; }
    }

    public static void main(String[] args) {
        boolean result = switch (args.length == 0 ? "all" : args[0]) {
            case "firstFactory" -> firstFactory();
            case "typed" -> typed();
            case "rejectsRecord" -> rejectsRecord();
            case "all" -> firstFactory() && typed() && rejectsRecord();
            default -> throw new IllegalArgumentException(args[0]);
        };
        if (!result) throw new AssertionError();
    }
}
