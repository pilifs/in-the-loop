/** Observations of an already obtained receiver. These methods never choose its producer. */
public final class InventoryChecks {
    public static boolean nonnegative(Checkout.Pair p) { return p.primary().remaining() >= 0; }
    public static boolean taken(Checkout.Pair p, int count) { return p.primary().take() == (count > 0); }
    public static boolean aliasLaw(Checkout.Pair p) {
        int before = p.backup().remaining();
        boolean same = p.primary() == p.backup();
        boolean positive = p.primary().remaining() > 0;
        p.primary().take();
        return p.backup().remaining() == before - (same && positive ? 1 : 0);
    }
    public static boolean unchanged(Checkout.Pair p) {
        int before = p.backup().remaining(); p.primary().take(); return p.backup().remaining() == before;
    }
    public static boolean shared(Checkout.Pair p) { return p.primary() == p.backup(); }
    public static boolean distinct(Checkout.Pair p) { return p.primary() != p.backup(); }
}
