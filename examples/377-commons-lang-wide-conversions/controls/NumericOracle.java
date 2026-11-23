import org.apache.commons.lang3.math.Fraction;
import org.apache.commons.lang3.mutable.MutableDouble;

public final class NumericOracle {
    public static void main(String[] args) {
        int failures = 0;
        for (int n = 1 << 24; n < 1 << 25; n++) {
            double got = Fraction.getFraction(n, 2).floatValue();
            int floor = n >>> 1;
            if (got != floor + ((n & 3) == 3 ? 1 : 0)) throw new AssertionError(n);
            if (got != floor) failures++;
        }
        if (failures != 4194304 || Fraction.getFraction(33554431, 2).floatValue() != 16777216.0)
            throw new AssertionError(failures);
        long[] words = {0x41e0000000000000L, 0x41e0000000000001L, 0x41e8000000000000L, 0x41efffffffffffffL};
        for (long word : words) {
            double x = Double.longBitsToDouble(word);
            MutableDouble d = new MutableDouble(x);
            if (d.intValue() != Integer.MAX_VALUE || d.intValue() == (int)(long)x) throw new AssertionError(word);
            d.setValue(-x);
            if (d.intValue() != Integer.MIN_VALUE) throw new AssertionError(word);
        }
        System.out.println("16777216 rational inputs, 4194304 floor mismatches; 4 binary64 boundary histories");
    }
}
