import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import org.apache.commons.fileupload2.core.MultipartInput;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        byte[] body = Base64.getDecoder().decode(args[0]);
        ByteArrayOutputStream wire = new ByteArrayOutputStream();
        wire.write("--Boundary7\r\nContent-Type: application/octet-stream\r\n\r\n".getBytes(StandardCharsets.US_ASCII));
        wire.write(body);
        wire.write("\r\n--Boundary7--\r\n".getBytes(StandardCharsets.US_ASCII));
        MultipartInput in = MultipartInput.builder().setBoundary("Boundary7".getBytes(StandardCharsets.US_ASCII))
                .setInputStream(new ByteArrayInputStream(wire.toByteArray())).get();
        if (!in.skipPreamble()) throw new IOException("no multipart part");
        in.readHeaders();
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        long count = in.readBodyData(output);
        return count + ":" + Base64.getEncoder().encodeToString(output.toByteArray());
    }
}
