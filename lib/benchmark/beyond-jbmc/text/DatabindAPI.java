import java.io.IOException;
import java.math.BigDecimal;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.exc.InvalidFormatException;

public final class DatabindAPI {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    public static long[] read(String text, int kind) throws IOException {
        Class<?> type = kind==0 ? Double.class : kind==1 ? Float.class : kind==2 ? BigDecimal.class : Number.class;
        Object v;
        try {
            v=MAPPER.readValue("\"" + text + "\"", type);
        } catch (InvalidFormatException e) {
            if (e.getClass()!=InvalidFormatException.class) throw e;
            return new long[]{1,0,0,0};
        }
        if (v instanceof Double) return new long[]{0,0,Double.doubleToRawLongBits((Double)v),0};
        if (v instanceof Float) return new long[]{0,1,Float.floatToRawIntBits((Float)v),0};
        if (v instanceof BigDecimal) {
            BigDecimal d=(BigDecimal)v;
            return new long[]{0,2,d.unscaledValue().longValueExact(),d.scale()};
        }
        if (v instanceof Integer) return new long[]{0,3,(Integer)v,0};
        if (v instanceof Long) return new long[]{0,4,(Long)v,0};
        if (v==null) return new long[]{0,5,0,0};
        throw new IllegalArgumentException("unregistered boxed number type");
    }
}
