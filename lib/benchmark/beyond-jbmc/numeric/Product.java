import javax.vecmath.Vector2f;

public final class Product {
    public static boolean range(float x, float y) {
        if (!(x >= 1f && x < 2f && y >= 2f && y < 4f)) return true;
        Vector2f v = new Vector2f(x, -x);
        v.scale(y);
        return v.x >= 2f && v.x < 8f && v.y == -v.x;
    }

    public static boolean underflow(float x, float y) {
        if (!(x >= 0x1p-75f && x < 0x1p-74f && y >= 0x1p-75f && y < 0x1p-74f)) return true;
        Vector2f v = new Vector2f(x, 0f);
        v.scale(y);
        boolean tie = x == 0x1p-75f && y == 0x1p-75f;
        return (v.x == 0f) == tie && (v.x == 0f || v.x == 0x1p-149f || v.x == 0x1p-148f);
    }

    public static boolean positive(float x, float y) {
        if (!(x >= 0x1p-75f && x < 0x1p-74f && y >= 0x1p-75f && y < 0x1p-74f)) return true;
        Vector2f v = new Vector2f(x, 0f);
        v.scale(y);
        return v.x > 0f;
    }

    public static boolean unrounded(float x, float y) {
        if (!(x >= 1f && x < 2f && y >= 2f && y < 4f)) return true;
        Vector2f v = new Vector2f(x, -x);
        v.scale(y);
        return (double)v.x == (double)x * (double)y;
    }
}
