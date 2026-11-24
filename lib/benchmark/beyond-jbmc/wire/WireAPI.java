import java.io.IOException;
import org.apache.lucene.store.ByteArrayDataInput;
import org.apache.lucene.store.ByteArrayDataOutput;

/** Compiled once against Lucene 8.11.0. Only the frame, cursor and primitive values cross versions. */
public final class WireAPI {
    public static int write(byte[] frame, int offset, int value) throws IOException {
        ByteArrayDataOutput out = new ByteArrayDataOutput(frame, offset, 4);
        out.writeInt(value);
        return out.getPosition();
    }

    public static long read(byte[] frame, int offset) throws IOException {
        ByteArrayDataInput in = new ByteArrayDataInput(frame, offset, 4);
        int value = in.readInt();
        return ((long) in.getPosition() << 32) | (value & 0xffffffffL);
    }

    public static int writeVInt(byte[] frame, int offset, int value) throws IOException {
        ByteArrayDataOutput out = new ByteArrayDataOutput(frame, offset, 5);
        out.writeVInt(value);
        return out.getPosition();
    }

    public static long readVInt(byte[] frame, int offset) throws IOException {
        ByteArrayDataInput in = new ByteArrayDataInput(frame, offset, 5);
        int value = in.readVInt();
        return ((long) in.getPosition() << 32) | (value & 0xffffffffL);
    }
}
