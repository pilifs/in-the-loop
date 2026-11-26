import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.google.protobuf.util.JsonFormat;
import reactor.core.publisher.Flux;
import org.springframework.core.ResolvableType;
import org.springframework.core.io.buffer.*;
import org.springframework.http.MediaType;
import org.springframework.http.codec.protobuf.ProtobufJsonEncoder;
import org.springframework.protobuf.*;

public class PublicCaller {
    static Msg message(int n) {
        return Msg.newBuilder().setFoo("value" + n).setBlah(SecondMsg.newBuilder().setBlah(n)).build();
    }
    public static String observe(String[] args) {
        var type = ResolvableType.forClass(Msg.class);
        var media = MediaType.parseMediaType(args[0].equals("ndjson") ? "application/x-ndjson" : "application/jsonl");
        var encoder = args[0].equals("default") ? new ProtobufJsonEncoder()
                : new ProtobufJsonEncoder(JsonFormat.printer().omittingInsignificantWhitespace());
        if (!encoder.canEncode(type,media)) return "not selected";
        var bytes = new ByteArrayOutputStream();
        var inputs = List.of(message(123), message(456));
        encoder.encode(Flux.fromIterable(inputs),DefaultDataBufferFactory.sharedInstance,type,media,Map.of()).doOnNext(b -> {
            try { byte[] part = new byte[b.readableByteCount()]; b.read(part); bytes.writeBytes(part); }
            finally { DataBufferUtils.release(b); }
        }).blockLast();
        String[] lines = bytes.toString(StandardCharsets.UTF_8).split("\n",-1);
        boolean terminated = lines[lines.length-1].isEmpty();
        var decoded = new ArrayList<String>();
        int count = lines.length - (terminated ? 1 : 0);
        for (int i=0; i<count; i++) {
            try {
                var b = Msg.newBuilder(); JsonFormat.parser().merge(lines[i],b);
                int nested = b.getBlah().getBlah();
                decoded.add(message(nested).equals(b.build()) ? String.valueOf(nested) : "changed");
            } catch (com.google.protobuf.InvalidProtocolBufferException e) { decoded.add("invalid"); }
        }
        return "lines=" + count + " terminated=" + terminated + " decoded=" + decoded;
    }
}
