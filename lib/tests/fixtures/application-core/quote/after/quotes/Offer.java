package quotes;

/** A standing offer for a code: a DTO with primitive fields. */
public final class Offer {
    final long unitCents;
    final int minimumUnits;

    public Offer(long unitCents, int minimumUnits) {
        this.unitCents = unitCents;
        this.minimumUnits = minimumUnits;
    }
}
