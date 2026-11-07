package shop;

// Defect 'duplicated-effect': two events for a bulk order.

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** The thin entry point in front of the kernel. */
@RestController
public class QuotesController {
    private final KafkaTemplate<String, QuoteEvent> kafka;

    public QuotesController(KafkaTemplate<String, QuoteEvent> kafka) {
        this.kafka = kafka;
    }

    @PostMapping("/quotes")
    public long quote(@RequestParam long cents, @RequestParam int quantity) {
        long total = Pricing.total(new Quote(new Money(cents), quantity));
        if (total > 0) {
            kafka.send("quotes", new QuoteEvent(total, quantity));
            if (quantity >= 10) kafka.send("quotes", new QuoteEvent(total, quantity));
        }
        return total;
    }

    /** The case this loop leaves unresolved: a string response, built by string concatenation. */
    @PostMapping("/quotes/text")
    public String quoteText(@RequestParam long cents, @RequestParam int quantity) {
        return "total " + Pricing.total(new Quote(new Money(cents), quantity));
    }
}
