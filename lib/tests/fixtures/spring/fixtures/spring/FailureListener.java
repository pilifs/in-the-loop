package fixtures.spring;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

/** A listener's throws line has no outcomes: the container's error handler decides. */
@Component
public class FailureListener {
    private final FailureFlow flow;

    public FailureListener(FailureFlow flow) {
        this.flow = flow;
    }

    @KafkaListener(topics = "failures")
    public void on(String id) {
        flow.expire(id);
        flow.check(id);
    }
}
