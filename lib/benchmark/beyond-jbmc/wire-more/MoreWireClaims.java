import java.io.IOException;

public final class MoreWireClaims {
    static int size(long bits) {
        int n = 1;
        while ((bits & ~127L) != 0) { bits >>>= 7; ++n; }
        return n;
    }

    static boolean shorts(short v, boolean oldWriter, boolean oldReader) throws IOException {
        byte[] b = {0x33, 0, 0, 0x55};
        int end = oldWriter ? before.WireMore.putShort(b, v) : WireMore.putShort(b, v);
        long[] read = oldReader ? before.WireMore.shortValue(b) : WireMore.shortValue(b);
        short expected = oldWriter == oldReader ? v : (short)(((v & 255) << 8) | ((v & 0xffff) >>> 8));
        return read[0] == expected && read[1] == end && end == 3 && b[0] == 0x33 && b[3] == 0x55;
    }
    static boolean longs(long v, boolean oldWriter, boolean oldReader) throws IOException {
        byte[] b = new byte[10];
        b[0] = 0x33; b[9] = 0x55;
        int end = oldWriter ? before.WireMore.putLong(b, v) : WireMore.putLong(b, v);
        long[] read = oldReader ? before.WireMore.longValue(b) : WireMore.longValue(b);
        return read[0] == (oldWriter == oldReader ? v : Long.reverseBytes(v)) && read[1] == end && end == 9
                && b[0] == 0x33 && b[9] == 0x55;
    }
    public static boolean shortOldNew(short v) throws IOException { return shorts(v, true, false); }
    public static boolean shortNewOld(short v) throws IOException { return shorts(v, false, true); }
    public static boolean longOldNew(long v) throws IOException { return longs(v, true, false); }
    public static boolean longNewOld(long v) throws IOException { return longs(v, false, true); }

    public static boolean size32(int n) {
        int size = size(n & 0xffffffffL);
        return before.ProtoAPI.size32(n) == size && ProtoAPI.size32(n) == size;
    }
    public static boolean size64(long n) {
        int size = size(n);
        return before.ProtoAPI.size64(n) == size && ProtoAPI.size64(n) == size;
    }

    public static boolean protoToLucene(int n) throws IOException {
        byte[] b = {0x33, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55};
        int length = size(n & 0xffffffffL);
        int wrote = ProtoAPI.write32(b, length, n);
        int bits = n;
        for (int i=0; i<length; ++i) {
            int group = bits & 127;
            bits >>>= 7;
            if (b[1+i] != (byte)(bits == 0 ? group : group | 128)) return false;
        }
        long read = before.WireAPI.readVInt(b, 1);
        return wrote == length && (int)read == n && (read >>> 32) == 1+length && b[0]==0x33 && b[1+length]==0x55;
    }

    public static boolean swappedEntrypoint(int n) throws IOException {
        return ProtoAPI.signedInt32Bytes(n) == size(n & 0xffffffffL);
    }

    static boolean frame(long n, boolean oldWriter, int kind) throws IOException {
        long bits = kind == 32 ? n & 0xffffffffL : kind == 64 ? n : (n << 1) ^ (n >> 63);
        int size = size(bits);
        int declared;
        if (kind == 32) declared = oldWriter ? before.ProtoAPI.size32((int)n) : ProtoAPI.size32((int)n);
        else if (kind == 64) declared = oldWriter ? before.ProtoAPI.size64(n) : ProtoAPI.size64(n);
        else declared = oldWriter ? before.ProtoAPI.sintSize(n) : ProtoAPI.sintSize(n);
        byte[] b = new byte[13];
        b[0]=0x33; b[1+size]=8; b[2+size]=0x55;
        int written;
        if (kind == 32) written = oldWriter ? before.ProtoAPI.write32(b,size,(int)n) : ProtoAPI.write32(b,size,(int)n);
        else written = oldWriter ? before.ProtoAPI.write64(b,size,n,kind!=64) : ProtoAPI.write64(b,size,n,kind!=64);
        long[] result = oldWriter ? ProtoAPI.read(b,size,kind) : before.ProtoAPI.read(b,size,kind);
        return declared==size && written==size && result[0]==n && result[1]==size && result[2]==8 && result[3]==size+1
                && b[0]==0x33 && b[2+size]==0x55;
    }
    public static boolean uint32OldNew(int n) throws IOException { return frame(n,true,32); }
    public static boolean uint32NewOld(int n) throws IOException { return frame(n,false,32); }
    public static boolean uint64OldNew(long n) throws IOException { return frame(n,true,64); }
    public static boolean uint64NewOld(long n) throws IOException { return frame(n,false,64); }
    public static boolean sint64OldNew(long n) throws IOException { return frame(n,true,-64); }
    public static boolean sint64NewOld(long n) throws IOException { return frame(n,false,-64); }

    static boolean record(int header, int payload, boolean oldWriter) throws IOException {
        byte[] b = new byte[11];
        int end = 5 + size(payload & 0xffffffffL);
        b[0]=0x33; b[end]=0x55;
        int written = oldWriter ? before.WireMore.putRecord(b,header,payload) : WireMore.putRecord(b,header,payload);
        int[] result = oldWriter ? WireMore.record(b) : before.WireMore.record(b);
        return result[0]==Integer.reverseBytes(header) && result[1]==payload && result[2]==end && written==end
                && b[0]==0x33 && b[end]==0x55;
    }
    public static boolean recordOldNew(int header, int payload) throws IOException { return record(header,payload,true); }
    public static boolean recordNewOld(int header, int payload) throws IOException { return record(header,payload,false); }
}
