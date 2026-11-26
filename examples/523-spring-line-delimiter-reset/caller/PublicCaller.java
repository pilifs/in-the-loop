import org.springframework.core.ResolvableType;
import org.springframework.core.codec.StringDecoder;
import org.springframework.core.io.buffer.*;
import org.springframework.util.MimeType;

import reactor.core.publisher.Flux;

import java.nio.charset.StandardCharsets;
import java.util.*;

public class PublicCaller {
    static String decode(String text, boolean split) {
        byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
        var buffers = new ArrayList<DataBuffer>();
        var factory = new DefaultDataBufferFactory();
        if (split) for (byte b : bytes) buffers.add(factory.wrap(new byte[] {b}));
        else buffers.add(factory.wrap(bytes));
        return StringDecoder.allMimeTypes()
                .decode(
                        Flux.fromIterable(buffers),
                        ResolvableType.forClass(String.class),
                        new MimeType("text", "plain", StandardCharsets.UTF_8),
                        Map.of())
                .collectList()
                .block()
                .toString()
                .replace("\r", "<CR>");
    }

    public static String observe(String[] args) {
        if (args[0].equals("standard"))
            return decode("a\r\nb", false) + " / " + decode("a\nb", false);
        if (args[0].equals("chunks"))
            return decode("é\r\r\nZ", false) + " / " + decode("é\r\r\nZ", true);
        return decode("a\rXY\nb", false);
    }
}
