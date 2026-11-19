package shop;

import java.util.ArrayList;
import java.util.List;
import org.springframework.kafka.core.KafkaTemplate;

public final class QuoteCases {
    static final class Recorder extends KafkaTemplate<String, QuoteEvent> {
        final List<String> sends = new ArrayList<>();
        @Override public Object send(String topic, QuoteEvent data) {
            sends.add(String.format("{\"topic\":\"%s\",\"total\":%d,\"quantity\":%d}", topic, data.total(), data.quantity()));
            return null;
        }
    }

    public static void main(String[] quantities) {
        for (String input : quantities) {
            int quantity = Integer.parseInt(input);
            Recorder recorder = new Recorder();
            long amount = new QuotesController(recorder).quote(1L, quantity);
            System.out.printf("{\"cents\":1,\"quantity\":%d,\"amount\":%d,\"sends\":[%s]}%n",
                              quantity, amount, String.join(",", recorder.sends));
        }
    }
}
