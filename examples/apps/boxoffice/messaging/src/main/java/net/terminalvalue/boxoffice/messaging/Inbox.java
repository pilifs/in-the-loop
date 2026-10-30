package net.terminalvalue.boxoffice.messaging;

import static org.springframework.data.mongodb.core.query.Criteria.where;
import static org.springframework.data.mongodb.core.query.Query.query;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import net.terminalvalue.boxoffice.contracts.Message;
import org.springframework.data.annotation.Id;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.index.Index;
import org.springframework.data.mongodb.core.mapping.Document;

/**
 * The idempotent-consumer record. Kafka delivers at least once, so a consumer records each message's ID in the same
 * transaction as the changes the message causes. A redelivered message then finds its ID and is skipped. Together
 * with the {@link Outbox}, this gives exactly-once effects over at-least-once delivery.
 */
public final class Inbox {

    @Document(Inbox.COLLECTION)
    record Entry(@Id String id, Instant processedAt) {}

    static final String COLLECTION = "inbox";

    /** How long a message ID is remembered. Redelivery after that would be processed again. */
    static final Duration RETENTION = Duration.ofDays(30);

    private final MongoTemplate mongo;
    private final Clock clock;

    public Inbox(MongoTemplate mongo, Clock clock) {
        this.mongo = mongo;
        this.clock = clock;
        mongo.indexOps(Entry.class)
                .createIndex(new Index().on("processedAt", Sort.Direction.ASC).expire(RETENTION));
    }

    /**
     * Records that {@code consumer} is processing {@code message}, and returns false if it already did. Must run
     * inside the transaction that applies the message, so the record commits or rolls back with it. Two concurrent
     * deliveries of one message conflict on the insert, and the transaction retry then sees the record.
     */
    public boolean firstDelivery(String consumer, Message message) {
        Transactions.requireActive("Inbox.firstDelivery");
        String id = consumer + ":" + message.eventId();
        if (mongo.exists(query(where("_id").is(id)), Entry.class)) {
            return false;
        }
        mongo.insert(new Entry(id, clock.instant()));
        return true;
    }
}
