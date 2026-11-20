package chunks;
import java.nio.charset.StandardCharsets;
public final class Decoder {
    static Inputs.Result decode(byte[] bytes, int cuts) {
        ChunkInput in = new ChunkInput(bytes, cuts);
        byte[] buffer = new byte[16];
        StringBuilder result = new StringBuilder();
        int n;
        while ((n = in.read(buffer, 0, buffer.length)) != -1) result.append(new String(buffer, 0, n, StandardCharsets.UTF_8));
        return new Inputs.Result(result.toString(), in.read() == -1);
    }
}
