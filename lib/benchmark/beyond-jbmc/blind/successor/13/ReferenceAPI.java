import com.carrotsearch.hppc.BoundedProportionalArraySizingStrategy;

public final class ReferenceAPI {
    public static long primary(int n) {
        try { return new BoundedProportionalArraySizingStrategy().grow(0, 0, Integer.MAX_VALUE - 33 + n); }
        catch (RuntimeException ex) {
            if (ex.getClass().getSimpleName().equals("BufferAllocationException")) return -1;
            throw ex;
        }
    }
    public static long control(int n) { return new BoundedProportionalArraySizingStrategy().grow(10, 10, 1); }
}
