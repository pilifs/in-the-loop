import java.io.IOException;
import org.apache.lucene.store.ByteArrayDataInput;
import org.apache.lucene.store.ByteArrayDataOutput;
public final class PayloadFirst {
    public static int write(byte[] data,int header,int value) throws IOException {
        ByteArrayDataOutput out=new ByteArrayDataOutput(data,1,9);
        out.writeVInt(value);out.writeInt(header);
        return out.getPosition();
    }
    public static int[] read(byte[] data) throws IOException {
        ByteArrayDataInput in=new ByteArrayDataInput(data,1,9);
        return new int[]{in.readVInt(),in.readInt(),in.getPosition()};
    }
}
