package net.terminalvalue.boxoffice.system;

import static org.awaitility.Awaitility.await;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import net.terminalvalue.boxoffice.payments.PaymentApplication;
import net.terminalvalue.boxoffice.ticketing.TicketingApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.kafka.config.KafkaListenerEndpointRegistry;
import org.springframework.web.client.RestClient;
import org.testcontainers.kafka.KafkaContainer;
import org.testcontainers.mongodb.MongoDBContainer;

/**
 * The whole system: Kafka, a MongoDB replica set, and both services, each in its own Spring context. Started once per
 * JVM and shared by the tests.
 */
final class BoxOffice {

    static final Duration HOLD_TTL = Duration.ofSeconds(6);
    static final Duration SLOW_PAYMENT = Duration.ofSeconds(9);

    private static BoxOffice instance;

    final ConfigurableApplicationContext ticketing;
    final ConfigurableApplicationContext payments;
    final RestClient ticketingApi;
    final RestClient paymentsApi;

    static synchronized BoxOffice get() {
        if (instance == null) {
            instance = new BoxOffice();
        }
        return instance;
    }

    @SuppressWarnings("resource") // the containers live as long as the JVM; Testcontainers' Ryuk removes them
    private BoxOffice() {
        var kafka = new KafkaContainer("apache/kafka:4.2.1");
        var mongo = new MongoDBContainer("mongo:8.0").withReplicaSet();
        kafka.start();
        mongo.start();
        var common = new String[] {
            "--server.port=0",
            "--spring.kafka.bootstrap-servers=" + kafka.getBootstrapServers(),
            "--boxoffice.hold.ttl=" + HOLD_TTL.toSeconds() + "s",
            "--boxoffice.hold.sweep-interval=200ms",
            "--boxoffice.gateway.slow-delay=" + SLOW_PAYMENT.toSeconds() + "s",
        };
        ticketing = new SpringApplicationBuilder(TicketingApplication.class)
                .run(with(common, "--spring.mongodb.uri=" + mongo.getReplicaSetUrl("ticketing")));
        payments = new SpringApplicationBuilder(PaymentApplication.class)
                .run(with(common, "--spring.mongodb.uri=" + mongo.getReplicaSetUrl("payments")));
        ticketingApi = client(ticketing);
        paymentsApi = client(payments);
        awaitPartitionsAssigned(ticketing);
        awaitPartitionsAssigned(payments);
    }

    MongoTemplate ticketingDb() {
        return ticketing.getBean(MongoTemplate.class);
    }

    MongoTemplate paymentsDb() {
        return payments.getBean(MongoTemplate.class);
    }

    // HTTP helpers. Error statuses are returned, not thrown, so tests can assert on them.

    @SuppressWarnings("unchecked")
    static ResponseEntity<Map<String, Object>> post(RestClient api, String path, Object body, HttpHeaders headers) {
        return (ResponseEntity<Map<String, Object>>) (ResponseEntity<?>) api.post()
                .uri(path)
                .headers(h -> h.addAll(headers))
                .body(body == null ? Map.of() : body)
                .retrieve()
                .onStatus(_ -> true, (_, _) -> {})
                .toEntity(Map.class);
    }

    static ResponseEntity<Map<String, Object>> post(RestClient api, String path, Object body) {
        return post(api, path, body, new HttpHeaders());
    }

    @SuppressWarnings("unchecked")
    static Map<String, Object> get(RestClient api, String path) {
        return api.get().uri(path).retrieve().body(Map.class);
    }

    private static RestClient client(ConfigurableApplicationContext context) {
        return RestClient.create("http://localhost:" + context.getEnvironment().getProperty("local.server.port"));
    }

    private static void awaitPartitionsAssigned(ConfigurableApplicationContext context) {
        var registry = context.getBean(KafkaListenerEndpointRegistry.class);
        await().atMost(Duration.ofSeconds(60)).until(() -> registry.getListenerContainers().stream()
                .allMatch(c -> c.getAssignedPartitions() != null && !c.getAssignedPartitions().isEmpty()));
    }

    private static String[] with(String[] common, String... more) {
        return java.util.stream.Stream.concat(List.of(common).stream(), List.of(more).stream())
                .toArray(String[]::new);
    }
}
