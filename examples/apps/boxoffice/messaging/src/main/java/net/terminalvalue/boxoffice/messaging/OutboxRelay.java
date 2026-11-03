package net.terminalvalue.boxoffice.messaging;

import static org.springframework.data.mongodb.core.query.Criteria.where;
import static org.springframework.data.mongodb.core.query.Query.query;

import java.time.Clock;
import java.time.Duration;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Update;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;

/**
 * Publishes outbox entries to Kafka in insertion order, and marks each one published after Kafka acknowledges it.
 *
 * <p>A crash between the acknowledgement and the mark publishes the entry again on restart, so consumers must be
 * idempotent ({@link Inbox}). On a send failure the relay stops and retries from the same entry on the next poll,
 * so a later message about an order never overtakes an earlier one from the same instance.
 *
 * <p>Known limitation: two instances of a service would run two relays over the same outbox, which can publish an
 * entry twice and break per-order ordering. Running more than one instance needs a lease, so that one relay runs.
 */
public final class OutboxRelay {

    private static final Logger log = LoggerFactory.getLogger(OutboxRelay.class);

    private final MongoTemplate mongo;
    private final KafkaTemplate<String, String> kafka;
    private final Clock clock;
    private final int batchSize;
    private final Duration sendTimeout;

    public OutboxRelay(
            MongoTemplate mongo, KafkaTemplate<String, String> kafka, Clock clock, int batchSize, Duration sendTimeout) {
        this.mongo = mongo;
        this.kafka = kafka;
        this.clock = clock;
        this.batchSize = batchSize;
        this.sendTimeout = sendTimeout;
    }

    @Scheduled(fixedDelayString = "${boxoffice.outbox.poll-interval:100ms}")
    public void publishPending() {
        var pending = mongo.find(
                query(where("publishedAt").is(null))
                        .with(Sort.by("_id"))
                        .limit(batchSize),
                Outbox.Entry.class);
        for (Outbox.Entry entry : pending) {
            if (!send(entry)) {
                return;
            }
            mongo.updateFirst(
                    query(where("_id").is(entry.id())), new Update().set("publishedAt", clock.instant()), Outbox.Entry.class);
        }
    }

    private boolean send(Outbox.Entry entry) {
        try {
            kafka.send(entry.topic(), entry.key(), entry.payload()).get(sendTimeout.toMillis(), TimeUnit.MILLISECONDS);
            return true;
        } catch (ExecutionException | TimeoutException e) {
            log.warn("Publishing outbox entry {} to {} failed; will retry", entry.id(), entry.topic(), e);
            return false;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }
}
