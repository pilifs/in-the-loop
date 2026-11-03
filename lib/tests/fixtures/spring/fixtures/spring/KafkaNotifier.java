package fixtures.spring;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
public class KafkaNotifier implements Notifier {
    private final KafkaTemplate<String, String> kafka;

    public KafkaNotifier(KafkaTemplate<String, String> kafka) {
        this.kafka = kafka;
    }

    @Override
    public void notify(String who) {
        kafka.send("notices", who, "archived");
    }
}
