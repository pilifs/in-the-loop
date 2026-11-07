package shop;

// Defect 'route-change': the route is renamed and nothing else changes. Its obligation is changed, not proved, without a person's approval, and a cached result for the old route must not be reused.

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

    @PostMapping("/quote")
    public long quote(@RequestParam long cents, @RequestParam int quantity) {
        long total = Pricing.total(new Quote(new Money(cents), quantity));
        if (total > 0) kafka.send("quotes", new QuoteEvent(total, quantity));
        return total;
    }

    /** The case this loop leaves unresolved: a string response, built by string concatenation. */
    @PostMapping("/quotes/text")
    public String quoteText(@RequestParam long cents, @RequestParam int quantity) {
        return "total " + Pricing.total(new Quote(new Money(cents), quantity));
    }
}
