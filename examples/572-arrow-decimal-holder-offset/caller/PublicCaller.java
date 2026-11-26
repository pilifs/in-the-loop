import org.apache.arrow.memory.*;
import org.apache.arrow.vector.*;
import org.apache.arrow.vector.complex.impl.*;
import org.apache.arrow.vector.holders.*;

import java.math.BigDecimal;

public class PublicCaller {
    static BigDecimal num(String s) {
        return new BigDecimal(s);
    }

    static String trial(BufferAllocator alloc, boolean wide, String arg, boolean vary) {
        try (BaseFixedWidthVector v =
                wide
                        ? new Decimal256Vector("wide", alloc, 38, 2)
                        : new DecimalVector("decimal", alloc, 38, 2)) {
            v.allocateNew(3);
            BigDecimal[] vals = {
                num(arg.equals("control") ? "0.00" : vary ? "-9.99" : "1.23"),
                num(vary ? "42.42" : "1234567.89"),
                num("-1234567.89")
            };
            for (int i = 0; i < 3; i++) {
                if (wide) ((Decimal256Vector) v).setSafe(i, vals[i]);
                else ((DecimalVector) v).setSafe(i, vals[i]);
            }
            v.setValueCount(3);
            java.util.List<String> seen = new java.util.ArrayList<>();
            int[] indices =
                    arg.equals("control")
                            ? new int[] {0}
                            : arg.equals("intent") ? new int[] {1, 2} : new int[] {2};
            for (int i : indices) {
                BigDecimal value, other;
                if (wide) {
                    var h = new NullableDecimal256Holder();
                    ((Decimal256Vector) v).get(i, h);
                    value = new NullableDecimal256HolderReaderImpl(h).readBigDecimal();
                    var plain = new Decimal256Holder();
                    plain.start = h.start;
                    plain.buffer = h.buffer;
                    plain.precision = h.precision;
                    plain.scale = h.scale;
                    other = new Decimal256HolderReaderImpl(plain).readBigDecimal();
                } else {
                    var h = new NullableDecimalHolder();
                    ((DecimalVector) v).get(i, h);
                    value = new NullableDecimalHolderReaderImpl(h).readBigDecimal();
                    var plain = new DecimalHolder();
                    plain.start = h.start;
                    plain.buffer = h.buffer;
                    plain.precision = h.precision;
                    plain.scale = h.scale;
                    other = new DecimalHolderReaderImpl(plain).readBigDecimal();
                }
                if (!v.getObject(i).equals(vals[i]))
                    throw new AssertionError("vector readback differs from written decimal");
                seen.add(value + "=" + (arg.equals("challenge") ? other : v.getObject(i)));
            }
            return String.join("/", seen);
        }
    }

    public static String observe(String[] a) {
        try (var alloc = new RootAllocator()) {
            if (!a[0].equals("challenge")) return trial(alloc, false, a[0], false);
            return trial(alloc, false, a[0], false)
                    + "/"
                    + trial(alloc, true, a[0], false)
                    + " / "
                    + trial(alloc, false, a[0], true)
                    + "/"
                    + trial(alloc, true, a[0], true);
        }
    }
}
