import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.springframework.boot.buildpack.platform.io.*;

public class PublicCaller {
    public static String observe(String[] args) throws Exception {
        if (!args[0].equals("challenge")) {
            boolean control = args[0].equals("control");
            byte[] source = (control ? "test" : "xxxxxtest").getBytes(StandardCharsets.US_ASCII);
            var content = InspectedContent.of(out -> out.write(source, control ? 0 : 5, 4));
            var read = new ByteArrayOutputStream();
            content.writeTo(read);
            return content.size() + ":" + read.toString(StandardCharsets.US_ASCII);
        }
        byte[] source = new byte[4102];
        for (int i = 0; i < source.length; i++) source[i] = (byte) (i % 127);
        var content = InspectedContent.of(out -> { out.write(source, 0, 6); out.write(source, 6, 4096); });
        var archive = TarArchive.of(layout -> {
            layout.file("payload", Owner.ROOT, content);
            layout.file("marker", Owner.ROOT, Content.of(new byte[] {42}));
        });
        var bytes = new ByteArrayOutputStream();
        archive.writeTo(bytes);
        try (var reader = new TarArchiveInputStream(new ByteArrayInputStream(bytes.toByteArray()))) {
            var one = reader.getNextEntry();
            if (one == null || !one.getName().equals("payload")) return "missing-payload";
            boolean same = Arrays.equals(source, reader.readAllBytes());
            var next = reader.getNextEntry();
            if (next == null) return "missing-marker";
            boolean marker = Arrays.equals(new byte[] {42}, reader.readAllBytes());
            return one.getSize() + ":" + same + ":" + next.getName() + ":" + marker
                    + ":" + (reader.getNextEntry() == null ? "eof" : "extra");
        }
    }
}
