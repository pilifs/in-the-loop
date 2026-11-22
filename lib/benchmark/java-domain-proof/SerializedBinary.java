package campaign;
import java.nio.ByteBuffer;
import java.util.Arrays;
import org.apache.parquet.variant.Variant;

/** Separate entry with independently constructed wire bytes for the same public Variant lookup. */
public final class SerializedBinary {
    static byte[] value(int code) {
        int left = NestedBinary.length(code,0), right = NestedBinary.length(code,1);
        int start = NestedBinary.padding(code), width = 15 + left + right;
        byte[] bytes = new byte[start + width + 1];
        bytes[start] = 3;             // Small array, one-byte offsets.
        bytes[start+1] = 2;
        bytes[start+3] = (byte)(5 + left);
        bytes[start+4] = (byte)(10 + left + right);
        int child = start + 5;
        for (int index = 0; index < 2; index++) {
            int len = index == 0 ? left : right;
            bytes[child] = 60;        // Primitive binary, four-byte little-endian length.
            bytes[child+1] = (byte)len;
            for (int j=0; j<len; j++) bytes[child+5+j]=(byte)(10+10*index+j);
            child += 5+len;
        }
        bytes[bytes.length-1] = -1;
        return bytes;
    }
    static Variant parse(int code) {
        int start = NestedBinary.padding(code);
        byte[] value = value(code), meta = new byte[start + 4];
        meta[start] = 1;
        meta[meta.length-1] = -1;
        return new Variant(ByteBuffer.wrap(value,start,value.length-start-1),ByteBuffer.wrap(meta,start,3));
    }
    public static int extent(int code) {
        int index=NestedBinary.index(code);
        return NestedBinary.matches(parse(code).getElementAtIndex(index).getBinary(),index,NestedBinary.length(code,index));
    }
    public static int fresh(int code) {
        Variant root = parse(code);
        ByteBuffer before = root.getElementAtIndex(1).getBinary();
        int pos = before.position();
        while (before.hasRemaining()) before.get();
        ByteBuffer again = root.getElementAtIndex(1).getBinary();
        return again.position()==pos ? NestedBinary.matches(again,1,NestedBinary.length(code,1)) : 0;
    }
    static byte[] contents(ByteBuffer b) {
        byte[] bytes=new byte[b.remaining()];
        b.duplicate().get(bytes);
        return bytes;
    }
    public static void main(String[] args) {
        for (int code=0; code<64; code++) {
            Variant built=NestedBinary.container(code), serialized=parse(code);
            if (!Arrays.equals(contents(built.getValueBuffer()),contents(serialized.getValueBuffer()))
                    || !Arrays.equals(contents(built.getMetadataBuffer()),contents(serialized.getMetadataBuffer())))
                throw new AssertionError("builder/serialization " + code);
            int index=NestedBinary.index(code);
            ByteBuffer child=built.getElementAtIndex(index).getValueBuffer();
            ByteBuffer actual=built.getElementAtIndex(index).getBinary();
            int extent=extent(code),fresh=fresh(code);
            if (NestedBinary.extent(code)!=extent || NestedBinary.fresh(code)!=fresh) throw new AssertionError(code);
            System.out.printf("%d %d %d %d %d %d %d %d %b %b %s%n",code,extent,fresh,
                    built.getValueBuffer().capacity(),child.position(),actual.position(),actual.limit(),actual.remaining(),
                    actual.isReadOnly(),actual.hasArray(),actual.getClass().getName());
        }
    }
}
