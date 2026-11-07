package shop;

/** The pricing kernel. */
public final class Pricing {
    private Pricing() {}

    /** A tenth off an order of ten items or more. */
    static long discount(long gross, int quantity) {
        return quantity >= 10 ? gross / 10 : 0;
    }

    public static long total(Quote q) {
        long gross = q.cents * q.quantity;
        return gross - discount(gross, q.quantity);
    }

    /** The same quote for another quantity: changed in place and handed back. */
    public static Quote withQuantity(Quote q, int quantity) {
        q.quantity = quantity;
        return q;
    }
}
