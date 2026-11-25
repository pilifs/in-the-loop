import it.unimi.dsi.bits.Fast;

public final class ReferenceAPI {
    public static long primary(int n) {
        return Fast.nat2int(n);
    }
    public static long control(int n) {
        return Fast.int2nat(Fast.nat2int(n));
    }
}
