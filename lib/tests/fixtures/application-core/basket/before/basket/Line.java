package basket;

/** A line of a basket: a mutable quantity of a unit price. */
public final class Line {
    final long unitCents;
    int quantity;

    public Line(long unitCents, int quantity) {
        if (quantity < 0) {
            throw new IllegalArgumentException("negative quantity");
        }
        this.unitCents = unitCents;
        this.quantity = quantity;
    }
}
