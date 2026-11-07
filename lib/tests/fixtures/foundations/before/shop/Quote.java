package shop;

/** A quote: an amount in cents for each item, and how many items. Mutable, as many domain classes are. */
public final class Quote {
    long cents;
    int quantity;

    public Quote(long cents, int quantity) {
        if (quantity <= 0) throw new IllegalArgumentException();
        this.cents = cents;
        this.quantity = quantity;
    }

    public long cents() { return cents; }

    public int quantity() { return quantity; }
}
