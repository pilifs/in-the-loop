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
        long rate;
        try {
            rate = rates.rate(request.code);
        } catch (RateUnavailable e) {
            return -1;
        }
        long total = units(request.quantities) * rate + fee(request.quantities.length);
        if (Codes.vip(request.code)) {
            total -= total / 10;
        }
        if (total > 0) {
            events.send(new QuoteEvent(request.code, total));
        }
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
        long total = units * offer.unitCents + fee(request.quantities.length);
        if (total < floorCents) {
            total = floorCents;
        }
        return total;
    }

    /** The request itself, once it has a line: the caller keeps the same object. */
    public QuoteRequest checked(QuoteRequest request) {
        if (request.quantities.length == 0) {
            throw new IllegalArgumentException("a request has a line");
        }
        return request;
    }

    /** The fee: half of it for more than two lines. Reads the receiver's fee policy only. */
    long fee(int lines) {
        return lines > 2 ? feeCents / 2 : feeCents;
    }

    static long units(int[] quantities) {
        long units = 0;
        for (int q : quantities) {
            units += q;
        }
        return units;
    }
}
