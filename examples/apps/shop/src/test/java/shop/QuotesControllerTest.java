package shop;

import static shop.Tests.check;

import java.util.ArrayList;
import java.util.List;
import org.springframework.kafka.core.KafkaTemplate;

/**
 * The route against a template that records what it is asked to send. Each test goes through the route, the only
 * API whose signature every version keeps, and looks at the answer and at the last event sent, as a test of a Kafka
 * producer usually does.
 */
public final class QuotesControllerTest {

    private QuotesControllerTest() {}

    record Sent(String topic, Object data) {}

    static final class Recording extends KafkaTemplate<String, QuoteEvent> {
        final List<Sent> sent = new ArrayList<>();

        @Override
        public Object send(String topic, QuoteEvent data) {
            sent.add(new Sent(topic, data));
            return null;
        }

        Sent last() {
            return sent.get(sent.size() - 1);
        }
    }

    public static void quotesASmallOrderAtFullPrice() {
        Recording kafka = new Recording();
        check(new QuotesController(kafka).quote(250, 3) == 750, "three at 2.50 are 7.50");
        check(kafka.last().equals(new Sent("quotes", new QuoteEvent(750, 3))), "the quote is sent");
    }

    public static void takesATenthOffTenItemsOrMore() {
        Recording kafka = new Recording();
        check(new QuotesController(kafka).quote(100, 10) == 900, "ten at 1.00 are 9.00 after the discount");
        check(kafka.last().equals(new Sent("quotes", new QuoteEvent(900, 10))), "the discounted quote is sent");
    }

    public static void sendsNothingForAFreeQuote() {
        Recording kafka = new Recording();
        check(new QuotesController(kafka).quote(0, 5) == 0, "nothing costs nothing");
        check(kafka.sent.isEmpty(), "a free quote is not sent");
    }

    public static void refusesAnOrderOfNoItems() {
        Recording kafka = new Recording();
        try {
            new QuotesController(kafka).quote(100, 0);
            check(false, "an order of no items is refused");
        } catch (IllegalArgumentException expected) {
            check(kafka.sent.isEmpty(), "a refused order is not sent");
        }
    }

    public static void answersTheTextRouteWithTheTotal() {
        check(new QuotesController(new Recording()).quoteText(100, 2).equals("total 200"), "the text route says the total");
    }
}
