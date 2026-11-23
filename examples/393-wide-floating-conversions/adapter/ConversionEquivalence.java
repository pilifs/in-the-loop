import com.fasterxml.jackson.databind.node.DoubleNode;
import com.fasterxml.jackson.databind.node.LongNode;

public final class ConversionEquivalence {
    public static boolean classified(long n) {
        long base = 1L << 54;
        if (n < base || n >= 2 * base) return true;
        long k = n - base;
        long high = k >>> 31;
        long delta = (k & 0x7fffffffL) - (1L << 30);
        boolean mismatch = (high & 1) == 0 ? (delta == 1 || delta == 2) : (delta == -1 || delta == -2);
        LongNode node = new LongNode(n);
        float a = node.floatValue(), b = new DoubleNode(node.doubleValue()).floatValue();
        return (a != b) == mismatch;
    }
}
