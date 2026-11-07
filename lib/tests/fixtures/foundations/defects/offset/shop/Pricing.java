package shop;

// Defect 'offset': a cent too much per item. An input mapping before.cents = after.cents + 1 would make the totals agree; the anchored input must not get one.

/** The pricing kernel, over money. */
public final class Pricing {
    private Pricing() {}

    /** A tenth off an order of ten items or more, written the other way round: the changed pure helper. */
    static long discount(long gross, int quantity) {
        if (quantity < 10) return 0;
        return gross / 10;
    }

    public static long total(Quote q) {
        long gross = (q.amount.cents() + 1) * q.quantity;
        return gross - discount(gross, q.quantity);
    }

    /** The same quote for another quantity: changed in place and handed back. */
    public static Quote withQuantity(Quote q, int quantity) {
        q.quantity = quantity;
        return q;
    }
}
