package shop;

/** The pricing kernel, over money. */
public final class Pricing {
    private Pricing() {}

    /** A tenth off an order of ten items or more, the tenth taken first: the helper rewritten again. */
    static long discount(long gross, int quantity) {
        long tenth = gross / 10;
        return quantity >= 10 ? tenth : 0;
    }

    public static long total(Quote q) {
        long gross = q.amount.cents() * q.quantity;
        return gross - discount(gross, q.quantity);
    }

    /** The same quote for another quantity: changed in place and handed back. */
    public static Quote withQuantity(Quote q, int quantity) {
        q.quantity = quantity;
        return q;
    }
}
