import org.apache.commons.math3.geometry.euclidean.twod.Vector2D;

public final class DoubleProduct {
    public static boolean underflow(double x, double y) {
        if (!(x >= 0x1p-538 && x < 0x1p-537 && y >= 0x1p-537 && y < 0x1p-536)) return true;
        Vector2D input = new Vector2D(x, 0.0);
        double p = input.scalarMultiply(y).getX();
        boolean tie = x == 0x1p-538 && y == 0x1p-537;
        return (p == 0.0) == tie && (p == 0.0 || p == 0x1p-1074 || p == 0x1p-1073);
    }
}
