package net.terminalvalue.boxoffice.messaging;

import java.time.Clock;
import java.time.Duration;
import net.terminalvalue.boxoffice.contracts.Topics;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.mongodb.MongoDatabaseFactory;
import org.springframework.data.mongodb.MongoTransactionManager;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.kafka.config.TopicBuilder;
import org.springframework.kafka.core.KafkaAdmin;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.kafka.support.ExponentialBackOffWithMaxRetries;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.core.JacksonException;

/** Reliable messaging for a service. Import it from the application class. */
@Configuration(proxyBeanMethods = false)
@EnableScheduling
public class MessagingConfiguration {

    /** Partitions per topic. Records are keyed by order ID, so this bounds the consumers that run in parallel. */
    static final int PARTITIONS = 3;

    @Bean
    Clock clock() {
        return Clock.systemUTC();
    }

    /** MongoDB transactions need a replica set; a single-node one is enough. */
    @Bean
    MongoTransactionManager transactionManager(MongoDatabaseFactory factory) {
        return new MongoTransactionManager(factory);
    }

    @Bean
    Transactions transactions(MongoTransactionManager transactionManager) {
        return new Transactions(new TransactionTemplate(transactionManager), 5, Duration.ofMillis(20));
    }

    @Bean
    Outbox outbox(MongoTemplate mongo, Clock clock) {
        return new Outbox(mongo, clock);
    }

    @Bean
    Inbox inbox(MongoTemplate mongo, Clock clock) {
        return new Inbox(mongo, clock);
    }

    @Bean
    OutboxRelay outboxRelay(
            MongoTemplate mongo,
            KafkaTemplate<String, String> kafka,
            Clock clock,
            @Value("${boxoffice.outbox.batch-size:100}") int batchSize) {
        return new OutboxRelay(mongo, kafka, clock, batchSize, Duration.ofSeconds(10));
    }

    /**
     * Retries a failing record with exponential backoff, then moves it to {@code <topic>.DLT} so that one bad record
     * does not block its partition. A record that cannot be parsed goes there at once.
     */
    @Bean
    DefaultErrorHandler kafkaErrorHandler(KafkaTemplate<String, String> kafka) {
        var backOff = new ExponentialBackOffWithMaxRetries(6);
        backOff.setInitialInterval(100);
        backOff.setMultiplier(2.0);
        backOff.setMaxInterval(2_000);
        var handler = new DefaultErrorHandler(new DeadLetterPublishingRecoverer(kafka), backOff);
        handler.addNotRetryableExceptions(JacksonException.class);
        return handler;
    }

    /** Topics are created on startup if missing. Each dead-letter topic has as many partitions as its source. */
    @Bean
    KafkaAdmin.NewTopics topics() {
        return new KafkaAdmin.NewTopics(
                TopicBuilder.name(Topics.PAYMENT_COMMANDS).partitions(PARTITIONS).build(),
                TopicBuilder.name(Topics.PAYMENT_EVENTS).partitions(PARTITIONS).build(),
                TopicBuilder.name(Topics.PAYMENT_COMMANDS + Topics.DEAD_LETTER_SUFFIX).partitions(PARTITIONS).build(),
                TopicBuilder.name(Topics.PAYMENT_EVENTS + Topics.DEAD_LETTER_SUFFIX).partitions(PARTITIONS).build());
    }
}
