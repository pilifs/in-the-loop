package campaign;

import java.nio.BufferUnderflowException;
import java.nio.ByteBuffer;
import org.apache.parquet.variant.Variant;
import org.apache.parquet.variant.VariantArrayBuilder;
import org.apache.parquet.variant.VariantBuilder;

public final class NestedBinary {
    static int length(int code, int index) { return (code >> (index == 0 ? 0 : 2)) & 3; }
    static int index(int code) { return (code >> 4) & 1; }
    static int padding(int code) { return code < 32 ? 0 : 25; }

    static ByteBuffer payload(int code, int index) {
        byte[] data = new byte[length(code, index)];
        for (int j = 0; j < data.length; j++) data[j] = (byte) (10 + 10 * index + j);
        return ByteBuffer.wrap(data);
    }

    static ByteBuffer rewrap(ByteBuffer source, int offset) {
        int width = source.remaining();
        byte[] data = new byte[offset + width + 1];
        data[data.length - 1] = -1;
        source.duplicate().get(data, offset, width);
        return ByteBuffer.wrap(data, offset, width);
    }

    static Variant container(int code) {
        VariantBuilder root = new VariantBuilder();
        VariantArrayBuilder array = root.startArray();
        array.appendBinary(payload(code, 0));
        array.appendBinary(payload(code, 1));
        root.endArray();
        Variant original = root.build();
        return new Variant(rewrap(original.getValueBuffer(), padding(code)),
                           rewrap(original.getMetadataBuffer(), padding(code)));
    }

    static boolean exhausted(ByteBuffer view) {
        try {
            view.get();
            return false;
        } catch (BufferUnderflowException expected) {
            return true;
        }
    }

    static int matches(ByteBuffer view, int index, int width) {
        if (view.remaining() != width) return 0;
        for (int j = 0; j < width; j++) if (view.get() != 10 + 10 * index + j) return 0;
        return exhausted(view) ? 1 : 0;
    }

    public static int extent(int code) {
        int i = index(code);
        return matches(container(code).getElementAtIndex(i).getBinary(), i, length(code, i));
    }

    public static int fresh(int code) {
        Variant array = container(code);
        ByteBuffer last = array.getElementAtIndex(1).getBinary();
        int start = last.position();
        while (last.hasRemaining()) last.get();
        ByteBuffer again = array.getElementAtIndex(1).getBinary();
        return again.position() == start ? matches(again, 1, length(code, 1)) : 0;
    }
}
