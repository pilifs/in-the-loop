import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.springframework.core.ResolvableType;
import org.springframework.http.converter.multipart.*;
import org.springframework.util.MultiValueMap;

public class PublicCaller {
    static String parse(byte[] wire) throws Exception {
        var type = ResolvableType.forClassWithGenerics(MultiValueMap.class,String.class,Part.class);
        var parts = new MultipartHttpMessageConverter().read(type,new WireInput(wire),null);
        var fields = new ArrayList<String>();
        for (var entry : parts.entrySet()) {
            var values = new ArrayList<String>();
            for (Object raw : entry.getValue()) {
                var part = (FormFieldPart)raw;
                if (!entry.getKey().equals(part.name())) throw new AssertionError(part.name());
                values.add(part.value().isEmpty() ? "<empty>" : part.value());
            }
            fields.add(entry.getKey() + "=" + values);
        }
        return String.join(";",fields);
    }
    static byte[] resource(String name) throws IOException {
        try (var in = PublicCaller.class.getResourceAsStream("/org/springframework/http/multipart/" + name + ".multipart")) {
            return Objects.requireNonNull(in).readAllBytes();
        }
    }
    public static String observe(String[] args) throws Exception {
        if (args[0].equals("edges"))
            return parse(resource("servlet-empty-part")) + " / " + parse(resource("servlet-empty-last-part"));
        boolean one = args[0].equals("one");
        var body = new StringBuilder();
        for (String value : one ? List.of("a") : List.of("","a",""))
            body.append("--boundary\r\nContent-Disposition: form-data; name=\"").append(one ? "text1" : "item")
                    .append("\"\r\n\r\n").append(value).append("\r\n");
        return parse(body.append("--boundary--\r\n").toString().getBytes(StandardCharsets.UTF_8));
    }
}
