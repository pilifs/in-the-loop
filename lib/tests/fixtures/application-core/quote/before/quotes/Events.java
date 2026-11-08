package quotes;

/** Where quote events go. */
public interface Events {
    void send(QuoteEvent event);
}
