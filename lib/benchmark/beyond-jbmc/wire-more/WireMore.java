import java.io.IOException;
import org.apache.lucene.store.ByteArrayDataInput;
import org.apache.lucene.store.ByteArrayDataOutput;

public final class WireMore {
    public static int putShort(byte[] b, short v) throws IOException {
        ByteArrayDataOutput out = new ByteArrayDataOutput(b, 1, 2);
        out.writeShort(v);
        return out.getPosition();
    }
    public static int putLong(byte[] b, long v) throws IOException {
        ByteArrayDataOutput out = new ByteArrayDataOutput(b, 1, 8);
        out.writeLong(v);
        return out.getPosition();
    }
    public static long[] shortValue(byte[] b) throws IOException {
        ByteArrayDataInput in = new ByteArrayDataInput(b, 1, 2);
        return new long[]{in.readShort(), in.getPosition()};
    }
    public static long[] longValue(byte[] b) throws IOException {
        ByteArrayDataInput in = new ByteArrayDataInput(b, 1, 8);
        return new long[]{in.readLong(), in.getPosition()};
    }
    public static int putRecord(byte[] b, int header, int payload) throws IOException {
        ByteArrayDataOutput out = new ByteArrayDataOutput(b, 1, 9);
        out.writeInt(header);
        out.writeVInt(payload);
        return out.getPosition();
    }
    public static int[] record(byte[] b) throws IOException {
        ByteArrayDataInput in = new ByteArrayDataInput(b, 1, 9);
        return new int[]{in.readInt(), in.readVInt(), in.getPosition()};
    }
}
