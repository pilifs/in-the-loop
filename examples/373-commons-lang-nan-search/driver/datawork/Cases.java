package datawork;
import org.apache.commons.lang3.ArrayUtils;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static Object[] observe(double[] a, int start, int lo, int hi) {
        int[] indices = new int[hi - lo];
        for (int j = lo; j < hi; j++) indices[j-lo] = ArrayUtils.indexOf(a, Double.longBitsToDouble(NanSearch.BITS[j]), start, 0.0);
        long[] after = a == null ? null : new long[a.length];
        if (a != null) for (int i = 0; i < a.length; i++) after[i] = Double.doubleToRawLongBits(a[i]);
        return new Object[]{indices, after};
    }
    public static void main(String[] args) {
        double[] witness = {Double.NEGATIVE_INFINITY, Double.longBitsToDouble(NanSearch.BITS[0]),
                           Double.POSITIVE_INFINITY, -0.0, 0.0};
        if (ArrayUtils.indexOf(witness, Double.NEGATIVE_INFINITY, 0, 0.0) != 0
                || ArrayUtils.indexOf(witness, Double.POSITIVE_INFINITY, 0, 0.0) != 2
                || ArrayUtils.indexOf(witness, 0.0, 0, 0.0) != 3) throw new AssertionError("five-element controls");
        for (int code = 0; code < 902; code++) {
            long[] bits = NanSearch.source(code);
            int start = NanSearch.start(code);
            row(code,fields("bits",bits,"start",start),
                    fields("nans",observe(NanSearch.array(bits),start,0,2),"numbers",observe(NanSearch.array(bits),start,2,5)),
                    fields("nans",NanSearch.nans(code),"numbers",NanSearch.numbers(code)));
        }
    }
}
