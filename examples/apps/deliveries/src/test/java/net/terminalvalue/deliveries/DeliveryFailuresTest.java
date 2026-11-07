package net.terminalvalue.deliveries;

import static net.terminalvalue.deliveries.Tests.check;

import java.util.ArrayList;
import java.util.List;
import org.springframework.kafka.core.KafkaTemplate;

/**
 * The route against a template that records what it is asked to send. Each test looks at the answer and at the last
 * record sent, as a test of a Kafka producer usually does.
 */
public final class DeliveryFailuresTest {

    private DeliveryFailuresTest() {}

    record Sent(String topic, Object data) {}

    static final class Recording extends KafkaTemplate<String, Object> {
        final List<Sent> sent = new ArrayList<>();

        @Override
        public Object send(String topic, Object data) {
            sent.add(new Sent(topic, data));
            return null;
        }

        Sent last() {
            return sent.get(sent.size() - 1);
        }
    }

    public static void schedulesARetryWhenTheReceiverWasUnavailable() {
        Recording kafka = new Recording();
        check(new DeliveryFailures(kafka).failed(503, false, 1) == 202, "202 for a 503");
        check(kafka.last().equals(new Sent("delivery-retries", new RetryScheduled(503, 2))), "the next attempt is the second");
    }

    public static void retriesAnIdempotentDeliveryOnAServerError() {
        Recording kafka = new Recording();
        check(new DeliveryFailures(kafka).failed(500, true, 3) == 202, "202 for a 500 on an idempotent delivery");
        check(kafka.last().equals(new Sent("delivery-retries", new RetryScheduled(500, 4))), "the next attempt is the fourth");
    }

    public static void deadLettersANonIdempotentDeliveryThatMayHaveRun() {
        Recording kafka = new Recording();
        check(new DeliveryFailures(kafka).failed(500, false, 1) == 200, "200 for a 500 on a POST");
        check(kafka.last().equals(new Sent("delivery-dead-letters", new DeadLettered(500, 1))), "dead-lettered after one attempt");
    }

    public static void deadLettersADeliveryOutOfAttempts() {
        Recording kafka = new Recording();
        check(new DeliveryFailures(kafka).failed(503, true, 5) == 200, "200 once the fifth attempt failed");
        check(kafka.last().equals(new Sent("delivery-dead-letters", new DeadLettered(503, 5))), "dead-lettered after five attempts");
    }

    public static void neverRetriesWhatNoRetryCanFix() {
        Recording kafka = new Recording();
        check(new DeliveryFailures(kafka).failed(501, true, 1) == 200, "200 for a 501");
        check(kafka.last().topic().equals("delivery-dead-letters"), "a 501 is dead-lettered");
    }
}
