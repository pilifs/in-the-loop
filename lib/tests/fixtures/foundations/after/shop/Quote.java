package shop;

/** A quote: the amount for each item, as money, and how many items. */
public final class Quote {
    Money amount;
    int quantity;

    public Quote(Money amount, int quantity) {
        if (quantity <= 0) throw new IllegalArgumentException();
        this.amount = amount;
        this.quantity = quantity;
    }

    public Money amount() { return amount; }

    public int quantity() { return quantity; }
}
