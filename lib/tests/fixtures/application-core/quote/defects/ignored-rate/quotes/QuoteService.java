package quotes;

/** The service: an ordinary receiver with a fee policy and three dependencies. */
public class QuoteService {
    private final long feeCents;
    private final long floorCents;
    private final Rates rates;
    private final Offers offers;
    private final Events events;

    public QuoteService(long feeCents, long floorCents, Rates rates, Offers offers, Events events) {
        this.feeCents = feeCents;
        this.floorCents = floorCents;
        this.rates = rates;
        this.offers = offers;
        this.events = events;
    }

    /** The quote for a request: units times the code's rate, plus the fee, a tenth off for a VIP code; -1 without a rate. A positive quote is announced. */
    public long quote(QuoteRequest request) {
        String code = request.code;
        int[] quantities = request.quantities;
        long rate;
        try {
            rate = rates.rate(code);
        } catch (RateUnavailable e) {
            return -1;
        }
        long total = subtotal(quantities, 100) + fee(quantities.length); // DEFECT: the rate asked for, then ignored
        if (Codes.vip(code)) {
            total = total - total / 10;
        }
        if (total <= 0) {
            return total;
        }
        events.send(new QuoteEvent(code, total));
        return total;
    }

    /** The quote under the code's standing offer, never below the floor: -1 without an offer, 0 under its minimum. */
    public long offerQuote(QuoteRequest request) {
        Offer offer = offers.find(request.code);
        if (offer == null) {
            return -1;
        }
        long units = units(request.quantities);
        if (units < offer.minimumUnits) {
            return 0;
        }
        long total = subtotal(request.quantities, offer.unitCents) + fee(request.quantities.length);
        return total < floorCents ? floorCents : total;
    }

    /** The request itself, once it has a line: the caller keeps the same object. */
    public QuoteRequest checked(QuoteRequest request) {
        if (request.quantities.length > 0) {
            return request;
        }
        throw new IllegalArgumentException("a request has a line");
    }

    /** The fee: half of it for more than two lines. Reads the receiver's fee policy only. */
    long fee(int lines) {
        if (lines <= 2) {
            return feeCents;
        }
        return feeCents / 2;
    }

    private static long subtotal(int[] quantities, long unitCents) {
        return units(quantities) * unitCents;
    }

    static long units(int[] quantities) {
        long units = 0;
        for (int i = 0; i < quantities.length; i++) {
            units = units + quantities[i];
        }
        return units;
    }
}
