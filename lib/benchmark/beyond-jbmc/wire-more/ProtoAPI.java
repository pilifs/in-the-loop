import java.io.IOException;
import com.google.protobuf.CodedInputStream;
import com.google.protobuf.CodedOutputStream;

public final class ProtoAPI {
    public static int size32(int n) { return CodedOutputStream.computeUInt32SizeNoTag(n); }
    public static int size64(long n) { return CodedOutputStream.computeUInt64SizeNoTag(n); }
    public static int sintSize(long n) { return CodedOutputStream.computeSInt64SizeNoTag(n); }

    public static int write32(byte[] b, int size, int n) throws IOException {
        CodedOutputStream out = CodedOutputStream.newInstance(b, 1, size);
        out.writeUInt32NoTag(n);
        return out.getTotalBytesWritten();
    }
    public static int write64(byte[] b, int size, long n, boolean zigzag) throws IOException {
        CodedOutputStream out = CodedOutputStream.newInstance(b, 1, size);
        if (zigzag) out.writeSInt64NoTag(n); else out.writeUInt64NoTag(n);
        return out.getTotalBytesWritten();
    }
    public static int signedInt32Bytes(int n) throws IOException {
        CodedOutputStream out = CodedOutputStream.newInstance(new byte[10]);
        out.writeInt32NoTag(n);
        return out.getTotalBytesWritten();
    }
    public static long[] read(byte[] b, int size, int kind) throws IOException {
        CodedInputStream in = CodedInputStream.newInstance(b, 1, size + 1);
        long v = kind == 32 ? (long)in.readUInt32() : kind == 64 ? in.readUInt64() : in.readSInt64();
        int consumed = in.getTotalBytesRead();
        return new long[]{v, consumed, in.readTag(), in.getTotalBytesRead()};
    }
}
