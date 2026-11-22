package campaign;
import java.nio.ByteBuffer;
import org.apache.parquet.variant.Variant;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static Object observe(ByteBuffer view, int expectedWidth) {
        ByteBuffer all = view.duplicate();
        int[] bytes = new int[all.remaining()];
        for (int i = 0; i < bytes.length; i++) bytes[i] = all.get() & 255;
        for (int i = 0; i < expectedWidth && view.hasRemaining(); i++) view.get();
        return fields("bytes", bytes, "remaining", bytes.length, "exhausted", NestedBinary.exhausted(view));
    }

    public static void main(String[] args) {
        for (int code = 0; code < 64; code++) {
            int index = NestedBinary.index(code);
            Variant container = NestedBinary.container(code);
            ByteBuffer selected = container.getElementAtIndex(index).getBinary();
            Object extent = observe(selected, NestedBinary.length(code, index));
            ByteBuffer last = container.getElementAtIndex(1).getBinary();
            int start = last.position();
            while (last.hasRemaining()) last.get();
            ByteBuffer again = container.getElementAtIndex(1).getBinary();
            Object fresh = fields("sameStart", again.position() == start, "value", observe(again, NestedBinary.length(code, 1)));
            row(code, fields("left", NestedBinary.length(code, 0), "right", NestedBinary.length(code, 1),
                "index", index, "padding", NestedBinary.padding(code)), fields("extent", extent, "fresh", fresh),
                fields("extent", NestedBinary.extent(code), "fresh", NestedBinary.fresh(code)));
        }
    }
}
