package net.terminalvalue.boxoffice.contracts;

import java.time.Instant;
import java.util.UUID;

/** Fields that every message carries. */
public interface Message {

    /** Unique per message. Consumers deduplicate on it, because Kafka delivers at least once. */
    UUID eventId();

    /** The order the message is about. It is also the Kafka record key. */
    String orderId();

    Instant occurredAt();
}
