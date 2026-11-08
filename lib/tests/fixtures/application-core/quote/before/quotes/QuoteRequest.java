package quotes;

/** The request: a code and the quantities of its lines, as the client sent them. The array is the caller's. */
public final class QuoteRequest {
    final String code;
    final int[] quantities;

    public QuoteRequest(String code, int[] quantities) {
        if (code == null || quantities == null) {
            throw new IllegalArgumentException("a request has a code and quantities");
        }
        this.code = code;
        this.quantities = quantities;
    }
}
