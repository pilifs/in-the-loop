package net.terminalvalue.deliveries;

import net.terminalvalue.crosscut.retry.RetryPolicy;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Where a webhook dispatcher reports a delivery that failed: the receiver's HTTP status, whether the delivery may be
 * repeated safely, and how many attempts it has had, the failed one included. The route asks Crosscut's retry policy
 * whether to try again, and either schedules the next attempt on the retries topic (answering 202) or gives the
 * delivery up to the dead-letter topic (answering 200). The decision is the kernel's; the route only performs it.
 */
@RestController
public class DeliveryFailures {

    /** How many attempts a delivery gets in all. */
    static final int MAX_ATTEMPTS = 5;

    private final KafkaTemplate<String, Object> kafka;

    public DeliveryFailures(KafkaTemplate<String, Object> kafka) {
        this.kafka = kafka;
    }

    @PostMapping("/deliveries/failures")
    public int failed(@RequestParam int status, @RequestParam boolean idempotent, @RequestParam int attempts) {
        if (RetryPolicy.shouldRetry(status, idempotent, attempts, MAX_ATTEMPTS)) {
            kafka.send("delivery-retries", new RetryScheduled(status, attempts + 1));
            return 202;
        }
        kafka.send("delivery-dead-letters", new DeadLettered(status, attempts));
        return 200;
    }
}
