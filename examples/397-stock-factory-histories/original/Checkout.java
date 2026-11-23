public final class Checkout {
    public static final class Stock {
        private int left;
        public int remaining() { return left; }
        private Stock(int n) { left = n < 0 ? 0 : n; }
        public boolean take() {
            if (left == 0) return false;
            left--;
            return true;
        }
    }
    public static final class Pair {
        private final Stock primary, backup;
        public Stock primary() { return primary; }
        public Stock backup() { return backup; }
        private Pair(Stock primary, Stock backup) {
            this.primary = primary;
            this.backup = backup;
        }
        public static Pair open(int n, boolean shared) {
            Stock first = new Stock(n);
            return new Pair(first, shared ? first : new Stock(n));
        }
    }
    public static void raw(Pair p) {
        if (p != null && p.primary() != null) assert p.primary().remaining() >= 0;
    }
    public static void viaFactory(int n, boolean shared) {
        Pair p = Pair.open(n, shared);
        raw(p);
        int initial = n < 0 ? 0 : n;
        boolean taken = p.primary().take();
        assert taken == (n > 0);
        assert p.backup().remaining() == initial - (shared && n > 0 ? 1 : 0);
    }
    public static void assumesDistinct(int n, boolean shared) {
        Pair p = Pair.open(n, shared);
        int before = p.backup().remaining();
        p.primary().take();
        assert p.backup().remaining() == before;
    }
    public static void main(String[] args) {
        if (!Checkout.class.desiredAssertionStatus()) throw new IllegalStateException("Enable assertions");
        for (int n : new int[]{Integer.MIN_VALUE, -1, 0, 1, Integer.MAX_VALUE}) {
            viaFactory(n, true);
            viaFactory(n, false);
        }
        try { assumesDistinct(1, true); }
        catch (AssertionError expected) { System.out.println("Shared backup changed from 1 to 0"); return; }
        throw new AssertionError("False claim survived");
    }
}
