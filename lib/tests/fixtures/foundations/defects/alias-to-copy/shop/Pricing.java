package shop;

// Defect 'alias-to-copy': hands back a copy with the same values instead of the quote itself. Only the identity relation result == q tells them apart.

/** The pricing kernel, over money. */
public final class Pricing {
    private Pricing() {}

    /** A tenth off an order of ten items or more, written the other way round: the changed pure helper. */
    static long discount(long gross, int quantity) {
        if (quantity < 10) return 0;
        return gross / 10;
    }

    public static long total(Quote q) {
        long gross = q.amount.cents() * q.quantity;
        return gross - discount(gross, q.quantity);
    }

    /** The same quote for another quantity: changed in place and handed back. */
    public static Quote withQuantity(Quote q, int quantity) {
        q.quantity = quantity;
        // The copy is made for one item and then given the quantity, so that it agrees with q in every field for
        // every quantity, the constructor's refusal of a quantity below 1 included: identity is all that tells them
        // apart.
        Quote copy = new Quote(q.amount, 1);
        copy.quantity = quantity;
        return copy;
    }
}
