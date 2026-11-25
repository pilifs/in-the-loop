public final class IntegerCodec {
    public static int decode(int n) { return it.unimi.dsi.bits.Fast.nat2int(n); }
    public static int roundTrip(int n) { return it.unimi.dsi.bits.Fast.int2nat(decode(n)); }
    public static boolean primary(int n) {
        return n < 0 || decode(n) == (n % 2 == 0 ? n / 2 : -1 - n / 2);
    }
    public static boolean control(int n) { return n < 0 || roundTrip(n) == n; }
    public static boolean inverse(int n) { return n < 0 || !primary(n); }
    public static boolean unsigned(int n) {
        long bits = Integer.toUnsignedLong(n);
        int signed = (int) (bits % 2 == 0 ? bits / 2 : -1 - bits / 2);
        return decode(n) == signed;
    }
}
