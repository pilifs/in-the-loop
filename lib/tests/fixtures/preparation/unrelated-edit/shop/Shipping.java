package shop;

/** Shipping, which no route or kernel method reaches: the unrelated edit adds it. */
public final class Shipping {
    private Shipping() {}

    /** A flat fee per parcel of up to ten items. */
    public static long fee(int quantity) {
        return ((quantity + 9) / 10) * 450L;
    }
}
