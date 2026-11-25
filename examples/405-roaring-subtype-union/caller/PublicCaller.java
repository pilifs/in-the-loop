import java.util.Arrays;
import org.roaringbitmap.*;
import org.roaringbitmap.buffer.*;

public class PublicCaller {
    static class Sub extends MutableRoaringBitmap {}

    public static String observe(String[] args) {
        boolean base = args[0].equals("base");
        boolean permuted = args[0].equals("permuted");
        int[] order = permuted ? new int[]{3,1,0,2} : new int[]{0,1,2,3};
        RoaringBitmap[] heap = base ? new RoaringBitmap[4] : new FastRankRoaringBitmap[4];
        ImmutableRoaringBitmap[] buffer = base ? new ImmutableRoaringBitmap[4] : new Sub[4];
        int[][] heapBefore = new int[4][], bufferBefore = new int[4][];
        for (int j = 0; j < order.length; j++) {
            int i = order[j];
            var h = new FastRankRoaringBitmap();
            var b = new Sub();
            h.add((long) i, i + 10L);
            b.add((long) i, i + 10L);
            h.add(100_000 * i);
            b.add(100_000 * i);
            heap[j] = h;
            buffer[j] = b;
            heapBefore[j] = h.toArray();
            bufferBefore[j] = b.toArray();
        }
        var heapRefs = heap.clone();
        var bufferRefs = buffer.clone();
        String h, b;
        try { h = Arrays.toString(FastAggregation.priorityqueue_or(heap).toArray()); }
        catch (ArrayStoreException e) { h = e.getClass().getSimpleName(); }
        try { b = Arrays.toString(BufferFastAggregation.priorityqueue_or(buffer).toArray()); }
        catch (ArrayStoreException e) { b = e.getClass().getSimpleName(); }
        boolean heapSame = true, bufferSame = true;
        for (int j = 0; j < order.length; j++) {
            heapSame &= heap[j] == heapRefs[j] && Arrays.equals(heap[j].toArray(), heapBefore[j]);
            bufferSame &= buffer[j] == bufferRefs[j] && Arrays.equals(buffer[j].toArray(), bufferBefore[j]);
        }
        return "heap=" + h + "; buffer=" + b + (permuted ? "; heap inputs=" + heapSame + "; buffer inputs=" + bufferSame : "");
    }
}
