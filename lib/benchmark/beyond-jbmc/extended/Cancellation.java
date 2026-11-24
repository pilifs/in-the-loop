import javax.vecmath.Vector2f;

public final class Cancellation {
    // Factors are 1+n*2^-23 and 1-n*2^-23. The predecessor of 1 is 1-2^-24.
    private static float component(int n) {
        float x = Float.intBitsToFloat(0x3f800000 + n);
        float y = Float.intBitsToFloat(0x3f800000 - 2*n);
        Vector2f v = new Vector2f(x, -x);
        v.scaleAdd(y, new Vector2f(-1f, 1f));
        if (v.y != -v.x) throw new AssertionError();
        return v.x;
    }

    public static boolean rounds(int n) {
        if (n < 1 || n > 2048) return true;
        float expected = n <= 1448 ? 0f : -0x1p-24f;
        return Float.floatToRawIntBits(component(n)) == Float.floatToRawIntBits(expected);
    }

    public static boolean fused(int n) {
        if (n < 1 || n > 2048) return true;
        float exact = -((float)(n*n)) * 0x1p-46f;
        return Float.floatToRawIntBits(component(n)) == Float.floatToRawIntBits(exact);
    }
}
