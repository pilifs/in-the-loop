import java.nio.ByteBuffer;
import org.roaringbitmap.RoaringBitmap;
import org.roaringbitmap.buffer.ImmutableRoaringBitmap;
import org.roaringbitmap.buffer.MutableRoaringBitmap;

public class PublicCaller {
    static final long BLOCK = 1L << 16;
    static final long END = 1L << 32;

    static ImmutableRoaringBitmap snapshot(MutableRoaringBitmap live) {
        ByteBuffer bytes = ByteBuffer.allocate(live.serializedSizeInBytes());
        live.serialize(bytes);
        bytes.flip();
        return new ImmutableRoaringBitmap(bytes);
    }

    static String readers(RoaringBitmap heap, MutableRoaringBitmap live, long start, long end) {
        return heap.contains(start, end) + "/" + live.contains(start, end)
                + "/" + snapshot(live).contains(start, end);
    }

    public static String observe(String[] args) {
        if (args[0].equals("snapshot")) {
            MutableRoaringBitmap live = MutableRoaringBitmap.bitmapOf(-2, -1);
            ImmutableRoaringBitmap first = snapshot(live);
            long start = END - 2;
            String before = live.contains(start, END) + "/" + first.contains(start, END);
            live.add(0);
            String outside = live.contains(start, END) + "/" + first.contains(start, END);
            live.remove(-2);
            ImmutableRoaringBitmap second = snapshot(live);
            return "live/first=" + before + "," + outside + "," + live.contains(start, END)
                    + "/" + first.contains(start, END) + " second=" + second.contains(start, END)
                    + " counts=" + first.rangeCardinality(start, END) + "/" + second.rangeCardinality(start, END);
        }
        boolean control = args[0].equals("contained");
        long end = control ? BLOCK : BLOCK + 1;
        RoaringBitmap heap = RoaringBitmap.bitmapOfRange(0, BLOCK);
        MutableRoaringBitmap live = MutableRoaringBitmap.bitmapOfRange(0, BLOCK);
        String before = readers(heap, live, 0, end);
        heap.add((int) (3 * BLOCK));
        live.add((int) (3 * BLOCK));
        String low = "low=" + before + " withLater=" + readers(heap, live, 0, end);
        if (control) return low;
        return low + " top=" + readers(RoaringBitmap.bitmapOfRange(END - BLOCK, END),
                MutableRoaringBitmap.bitmapOfRange(END - BLOCK, END), END - BLOCK, END);
    }
}
