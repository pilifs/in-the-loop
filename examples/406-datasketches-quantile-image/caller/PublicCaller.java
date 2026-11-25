import java.lang.foreign.MemorySegment;
import java.util.Arrays;
import java.util.Comparator;
import org.apache.datasketches.common.ArrayOfStringsSerDe;
import org.apache.datasketches.kll.KllItemsSketch;
import static org.apache.datasketches.quantilescommon.QuantileSearchCriteria.INCLUSIVE;

public class PublicCaller {
    static String read(KllItemsSketch<String> s) {
        var v = s.getSortedView();
        return Arrays.toString(v.getQuantiles()) + " " + Arrays.toString(v.getCumulativeWeights())
                + " median=" + s.getQuantile(.5, INCLUSIVE) + " q55=" + s.getQuantile(.55, INCLUSIVE);
    }

    public static String observe(String[] args) {
        var comparator = Comparator.<String>naturalOrder();
        var serde = new ArrayOfStringsSerDe();
        var sketch = KllItemsSketch.newHeapInstance(8, comparator, serde);
        boolean reorder = args[0].equals("reordered");
        for (String item : (reorder ? "cadb" : "abcd").split("")) sketch.update(item);
        String first = args[0].equals("fresh") ? "" :
                "first=" + sketch.getQuantile(reorder ? .55 : .5, INCLUSIVE) + "; ";
        var image = MemorySegment.ofArray(sketch.toByteArray());
        String heap = read(KllItemsSketch.heapify(image, comparator, serde));
        return first + (reorder ? "heap=" + heap + "; wrap=" + read(KllItemsSketch.wrap(image, comparator, serde)) : heap);
    }
}
