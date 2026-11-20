package chunks;
import java.io.IOException;
public final class Decoder {
    static Inputs.Result decode(byte[] bytes, int cuts) throws IOException {
        return Inputs.read(new ChunkInput(bytes, cuts));
    }
}
