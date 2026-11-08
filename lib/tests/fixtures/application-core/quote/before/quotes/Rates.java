package quotes;

/** The dependency the service asks for a code's rate per unit, in cents: a read-only query. */
public interface Rates {
    long rate(String code) throws RateUnavailable;
}
