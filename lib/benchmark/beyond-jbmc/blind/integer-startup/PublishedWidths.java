import com.google.protobuf.CodedInputStream;
import com.google.protobuf.CodedOutputStream;
public final class PublishedWidths {
    public static boolean roundTrip(int n) {
        return n < 0 || CodedOutputStream.encodeZigZag32(CodedInputStream.decodeZigZag32(n)) == n;
    }
    private static int groups(long bits) {
        int count = 1;
        while ((bits >>>= 7) != 0) count++;
        return count;
    }
    public static boolean size32(int n) { return CodedOutputStream.computeUInt32SizeNoTag(n) == groups(n & 0xffffffffL); }
    public static boolean size64(long n) { return CodedOutputStream.computeUInt64SizeNoTag(n) == groups(n); }
    public static boolean wrong64(long n) { return !size64(n); }
}
