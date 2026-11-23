import com.fasterxml.jackson.databind.node.DoubleNode;
import com.fasterxml.jackson.databind.node.LongNode;
import org.apache.commons.lang3.mutable.MutableLong;

public final class NodeChecks {
    static final long BASE = 1L << 54;

    static long roundedInteger(long n) {
        long fraction = n - BASE;
        long high = fraction >>> 31;
        long low = fraction & 0x7fffffffL;
        long halfway = 1L << 30;
        if (low > halfway || (low == halfway && (high & 1L) != 0)) high++;
        return BASE + (high << 31);
    }

    public static boolean direct(long n) {
        if (n < BASE || n >= 2 * BASE) return true;
        return (double)new LongNode(n).floatValue() == (double)roundedInteger(n);
    }

    public static boolean same(long n) {
        if (n < BASE || n >= 2 * BASE) return true;
        LongNode node = new LongNode(n);
        return node.floatValue() == new DoubleNode(node.doubleValue()).floatValue();
    }

    public static boolean publicSubnormal(double x) {
        if (!(x >= 0x1p-150 && x <= 0x1p-149)) return true;
        return new DoubleNode(x).floatValue() == (x == 0x1p-150 ? 0f : 0x1p-149f);
    }

    public static boolean wrongSubnormal(double x) {
        if (!(x >= 0x1p-150 && x <= 0x1p-149)) return true;
        return new DoubleNode(x).floatValue() > 0;
    }

    public static boolean intrinsicSubnormal(double x) {
        if (!(x >= 0x1p-150 && x <= 0x1p-149)) return true;
        return (float)x == (x == 0x1p-150 ? 0f : 0x1p-149f);
    }

    public static boolean mantissaSubnormal(long k) {
        double x = Double.longBitsToDouble(0x3690000000000000L | (k & 0x000fffffffffffffL));
        return new DoubleNode(x).floatValue() == ((k & 0x000fffffffffffffL) == 0 ? 0f : 0x1p-149f);
    }

    public static boolean commons(long n) {
        if (n < BASE || n >= 2 * BASE) return true;
        return (double)new MutableLong(n).floatValue() == (double)roundedInteger(n);
    }
}
