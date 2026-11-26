import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import com.google.protobuf.util.JsonFormat;
import org.springframework.http.*;
import org.springframework.http.converter.protobuf.ProtobufHttpMessageConverter;
import org.springframework.protobuf.*;

public class PublicCaller {
    public static String observe(String[] args) throws Exception {
        try {
            Class.forName("com.googlecode.protobuf.format.JsonFormat");
            throw new AssertionError("alternative writer present");
        } catch (ClassNotFoundException expected) { }
        char[] letters = new char[12000];
        Arrays.fill(letters,'a');
        String text = args[0].equals("large") ? new String(letters) + "Ω" : "Foo";
        Msg input = Msg.newBuilder().setFoo(text).setBlah(SecondMsg.newBuilder().setBlah(123)).build();
        ProtobufHttpMessageConverter converter = new ProtobufHttpMessageConverter();
        MockHttpOutputMessage out = new MockHttpOutputMessage();
        if (args[0].equals("binary")) {
            converter.write(input, ProtobufHttpMessageConverter.PROTOBUF,out);
            return "roundtrip=" + input.equals(Msg.parseFrom(out.getBodyAsBytes())) + " schema="
                    + out.getHeaders().getFirst("X-Protobuf-Schema") + " message=" + out.getHeaders().getFirst("X-Protobuf-Message");
        }
        MediaType json = new MediaType("application","json",StandardCharsets.UTF_8);
        converter.write(input,json,out);
        boolean headers = json.equals(out.getHeaders().getContentType()) && !out.getHeaders().containsKey("X-Protobuf-Schema")
                && !out.getHeaders().containsKey("X-Protobuf-Message");
        byte[] body = out.getBodyAsBytes();
        if (body.length == 0) return "empty headers=" + headers;
        Msg.Builder parsed = Msg.newBuilder();
        try { JsonFormat.parser().merge(new String(body,StandardCharsets.UTF_8),parsed); }
        catch (java.io.IOException e) { return "incomplete bytes=" + body.length; }
        if (args[0].equals("small")) return "roundtrip=" + input.equals(parsed.build()) + " headers=" + headers;
        String foo = parsed.getFoo();
        return "roundtrip=" + input.equals(parsed.build()) + " length=" + foo.length() + " last=" + foo.charAt(foo.length()-1)
                + " nested=" + parsed.getBlah().getBlah();
    }
}
