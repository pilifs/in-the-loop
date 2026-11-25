import java.io.StringWriter;
import java.util.List;
import java.util.regex.Pattern;
import org.apache.avro.*;
import org.apache.avro.idl.IdlUtils;

public class PublicCaller {
    static String value(Object v) {
        if (v == null) return "null";
        if (v instanceof List<?> xs) return xs.stream().map(PublicCaller::value).toList().toString();
        return v.getClass().getSimpleName() + "(" + v + ")";
    }

    static String field(String union, String literal) throws Exception {
        var s = new Schema.Parser().parse("{\"type\":\"record\",\"name\":\"R\",\"namespace\":\"example\","
                + "\"fields\":[{\"name\":\"f\",\"type\":[" + union + "],\"default\":" + literal + "}]}");
        var f = s.getField("f");
        String decoded, idl;
        try { decoded = value(f.defaultVal()); }
        catch (AvroRuntimeException e) { decoded = e.getClass().getSimpleName(); }
        var writer = new StringWriter();
        try {
            IdlUtils.writeIdlSchema(writer, s);
            var match = Pattern.compile("\\bf\\s*=\\s*([^;]+);").matcher(writer.toString());
            idl = match.find() ? match.group(1).trim() : "initializer absent";
        } catch (AvroRuntimeException e) { idl = e.getClass().getSimpleName(); }
        return "present=" + f.hasDefaultValue() + "; value=" + decoded + "; idl=" + idl;
    }

    public static String observe(String[] args) throws Exception {
        String arr = "{\"type\":\"array\",\"items\":\"int\"}";
        return switch (args[0]) {
            case "null-first" -> field("\"null\",\"int\"", "1");
            case "int-first" -> field("\"int\",\"null\"", "1");
            case "array-orders" -> field(arr + ",\"int\"", "[1]") + " / " + field("\"int\"," + arr, "[1]");
            default -> throw new IllegalArgumentException();
        };
    }
}
