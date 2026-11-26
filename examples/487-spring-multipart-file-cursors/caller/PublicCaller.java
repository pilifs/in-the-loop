import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import org.springframework.core.ResolvableType;
import org.springframework.http.converter.multipart.*;
import org.springframework.util.MultiValueMap;

public class PublicCaller {
    static String read(InputStream in) throws IOException {
        return new String(in.readAllBytes(), StandardCharsets.UTF_8);
    }
    static String exercise(int threshold, boolean interleave) throws IOException {
        String body = "--boundary\r\nContent-Disposition: form-data; name=\"upload\"; filename=\"sample.txt\"\r\n"
                + "Content-Type: text/plain\r\n\r\nabcdef\r\n--boundary--\r\n";
        var c = new MultipartHttpMessageConverter();
        c.setMaxInMemorySize(threshold);
        var type = ResolvableType.forClassWithGenerics(MultiValueMap.class, String.class, Part.class);
        var parts = c.read(type, new WireInput(body.getBytes(StandardCharsets.UTF_8)), null);
        var part = (FilePart) parts.getFirst("upload");
        Path path = Path.of("copied.txt");
        try (var a = part.content()) {
            String prefix = interleave ? Character.toString(a.read()) : read(a);
            String second;
            try (var b = part.content()) { second = read(b); }
            Files.writeString(path, "a much longer old destination");
            part.transferTo(path);
            return prefix + "/" + second + "/" + Files.readString(path) + (interleave ? "/" + read(a) : "");
        } finally { part.delete(); Files.deleteIfExists(path); }
    }
    public static String observe(String[] args) throws IOException {
        if (args[0].equals("interleave")) return exercise(262144,true) + " | " + exercise(1,true);
        return exercise(args[0].equals("disk") ? 1 : 262144, false);
    }
}
