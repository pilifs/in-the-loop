package quotes;

/** What the service announces of a quote: its code and amount, snapshotted when sent. */
public final class QuoteEvent {
    final String code;
    final long amountCents;

    public QuoteEvent(String code, long amountCents) {
        this.code = code;
        this.amountCents = amountCents;
    }
}
