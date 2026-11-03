package net.terminalvalue.boxoffice.messaging;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import net.terminalvalue.boxoffice.contracts.Message;
import net.terminalvalue.boxoffice.contracts.MessageCodec;
import org.bson.types.ObjectId;
import org.springframework.data.annotation.Id;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.index.Index;
import org.springframework.data.mongodb.core.mapping.Document;

/**
 * The transactional outbox. A service never sends to Kafka while it changes its own state; it inserts the message
 * here, in the same MongoDB transaction as the state change. {@link OutboxRelay} publishes it afterwards. So a
 * message is published if and only if the change that caused it committed, at least once.
 */
public final class Outbox {

    /** One message waiting to be published, or published at {@code publishedAt}. */
    @Document(Outbox.COLLECTION)
    public record Entry(@Id ObjectId id, String topic, String key, String payload, Instant createdAt, Instant publishedAt) {}

    static final String COLLECTION = "outbox";

    private final MongoTemplate mongo;
    private final Clock clock;

    public Outbox(MongoTemplate mongo, Clock clock) {
        this.mongo = mongo;
        this.clock = clock;
        var indexes = mongo.indexOps(Entry.class);
        indexes.createIndex(new Index().on("publishedAt", Sort.Direction.ASC).on("_id", Sort.Direction.ASC));
        // Published entries are kept for a week, for debugging, then deleted. Pending entries have no publishedAt,
        // so the TTL monitor never deletes them.
        indexes.createIndex(new Index().named("published_ttl").on("publishedAt", Sort.Direction.ASC).expire(Duration.ofDays(7)));
    }

    /** Queues {@code message} for {@code topic}, keyed by its order ID. Must run inside the caller's transaction. */
    public void enqueue(String topic, Message message) {
        Transactions.requireActive("Outbox.enqueue");
        mongo.insert(new Entry(ObjectId.get(), topic, message.orderId(), MessageCodec.encode(message), clock.instant(), null));
    }
}
