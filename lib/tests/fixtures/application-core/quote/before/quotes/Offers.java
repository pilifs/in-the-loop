package quotes;

/** The dependency that finds a code's standing offer, or null when it has none. */
public interface Offers {
    Offer find(String code);
}
