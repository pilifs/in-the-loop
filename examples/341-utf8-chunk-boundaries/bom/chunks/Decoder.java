package chunks;
import java.io.IOException;
import org.apache.commons.io.ByteOrderMark;
import org.apache.commons.io.input.BOMInputStream;
public final class Decoder {
    static Inputs.Result decode(byte[] bytes, int cuts) throws IOException {
        byte[] withBom = new byte[bytes.length + 3];
        withBom[0] = (byte)239; withBom[1] = (byte)187; withBom[2] = (byte)191;
        System.arraycopy(bytes, 0, withBom, 3, bytes.length);
        ChunkInput chunks = new ChunkInput(withBom, (cuts << 3) | 4);
        return Inputs.read(BOMInputStream.builder().setInputStream(chunks).setByteOrderMarks(ByteOrderMark.UTF_8).setInclude(false).get());
    }
}
