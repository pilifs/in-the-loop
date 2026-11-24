public final class FactoryClaims {
    public static boolean nonnegative(int n, boolean same) { return InventoryChecks.nonnegative(Checkout.Pair.open(n,same)); }
    public static boolean taken(int n, boolean same) { return InventoryChecks.taken(Checkout.Pair.open(n,same),n); }
    public static boolean aliasLaw(int n, boolean same) { return InventoryChecks.aliasLaw(Checkout.Pair.open(n,same)); }
    public static boolean unchanged(int n, boolean same) { return InventoryChecks.unchanged(Checkout.Pair.open(n,same)); }
}
