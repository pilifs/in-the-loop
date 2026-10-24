package net.terminalvalue.boxoffice.system;

import static net.terminalvalue.boxoffice.system.BoxOffice.get;
import static net.terminalvalue.boxoffice.system.BoxOffice.post;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.springframework.data.mongodb.core.query.Criteria.where;
import static org.springframework.data.mongodb.core.query.Query.query;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.stream.Collectors;
import org.bson.Document;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.web.client.RestClient;

/**
 * The capabilities end to end, through the public HTTP APIs. After each test, once the system is quiet, the
 * cross-service invariants are checked directly against both databases.
 */
class BoxOfficeSystemTest {

    private static BoxOffice system;
    private static RestClient ticketing;
    private static RestClient payments;

    @BeforeAll
    static void start() {
        system = BoxOffice.get();
        ticketing = system.ticketingApi;
        payments = system.paymentsApi;
    }

    @Test
    void holdPayAndConfirm() {
        String concert = createConcert();
        String hold = hold(concert, "alice", "A1", "A2");

        var placed = post(ticketing, "/orders", Map.of("holdId", hold, "paymentToken", "tok_visa"));
        assertThat(placed.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(placed.getBody()).containsEntry("status", "PENDING_PAYMENT");
        String order = (String) placed.getBody().get("id");

        awaitOrderStatus(order, "CONFIRMED");
        assertThat(seats(concert)).containsEntry("A1", "SOLD").containsEntry("A2", "SOLD").containsEntry("A3", "AVAILABLE");
        assertThat(get(payments, "/payments/" + order))
                .containsEntry("status", "CAPTURED")
                .containsEntry("amountCents", 9000);
    }

    @Test
    void declinedPaymentReleasesTheSeats() {
        String concert = createConcert();
        String hold = hold(concert, "bob", "B1");
        String order = placeOrder(hold, "tok_declined");

        awaitOrderStatus(order, "DECLINED");
        assertThat(seats(concert)).containsEntry("B1", "AVAILABLE");
        assertThat(get(payments, "/payments/" + order)).containsEntry("status", "DECLINED");
    }

    @Test
    void cancellingAConfirmedOrderRefundsIt() {
        String concert = createConcert();
        String order = placeOrder(hold(concert, "carol", "A3"), "tok_visa");
        awaitOrderStatus(order, "CONFIRMED");

        var cancelled = post(ticketing, "/orders/" + order + "/cancellation", null);
        assertThat(cancelled.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(cancelled.getBody()).containsEntry("status", "REFUND_PENDING");
        assertThat(seats(concert)).containsEntry("A3", "AVAILABLE");

        awaitOrderStatus(order, "REFUNDED");
        assertThat(get(payments, "/payments/" + order)).containsEntry("status", "REFUNDED");
    }

    @Test
    void cancellingWhilePaymentIsInFlightIsRefused() {
        String concert = createConcert();
        String order = placeOrder(hold(concert, "dave", "A4"), "tok_slow");

        assertThat(post(ticketing, "/orders/" + order + "/cancellation", null).getStatusCode())
                .isEqualTo(HttpStatus.CONFLICT);
        // The slow charge outlives the hold, so the order ends refunded (see the next test).
        awaitOrderStatus(order, "REFUNDED");
    }

    /**
     * The race between a lease and a slow payment: the hold expires while the charge is in flight, someone else takes
     * the seat, and the first customer's money comes back.
     */
    @Test
    void paymentThatOutlivesItsHoldIsRefunded() {
        String concert = createConcert();
        String order = placeOrder(hold(concert, "erin", "A5"), "tok_slow");

        await().atMost(BoxOffice.HOLD_TTL.plusSeconds(5)).until(() -> seats(concert).get("A5").equals("AVAILABLE"));
        String frank = hold(concert, "frank", "A5");

        awaitOrderStatus(order, "REFUNDED");
        assertThat(get(payments, "/payments/" + order)).containsEntry("status", "REFUNDED");
        assertThat(get(ticketing, "/holds/" + frank)).containsEntry("customerId", "frank");
        assertThat(seats(concert)).containsEntry("A5", "HELD");
    }

    @Test
    void concurrentHoldsOnOneSeatHaveExactlyOneWinner() throws Exception {
        String concert = createConcert();
        int contenders = 16;
        List<Callable<HttpStatus>> attempts = new ArrayList<>();
        for (int i = 0; i < contenders; i++) {
            String customer = "fan-" + i;
            attempts.add(() -> HttpStatus.valueOf(post(
                                    ticketing,
                                    "/concerts/" + concert + "/holds",
                                    Map.of("customerId", customer, "seats", List.of("B2", "B3")))
                            .getStatusCode()
                            .value()));
        }
        List<HttpStatus> outcomes = new ArrayList<>();
        try (var pool = Executors.newFixedThreadPool(contenders)) {
            for (Future<HttpStatus> outcome : pool.invokeAll(attempts)) {
                outcomes.add(outcome.get());
            }
        }
        assertThat(outcomes).containsOnly(HttpStatus.CREATED, HttpStatus.CONFLICT);
        assertThat(outcomes).filteredOn(HttpStatus.CREATED::equals).hasSize(1);
        assertThat(system.ticketingDb()
                        .find(query(where("concertId").is(concert).and("status").is("HELD")), Document.class, "seats")
                        .stream()
                        .map(seat -> seat.getString("holdId"))
                        .distinct())
                .hasSize(1);
    }

    @Test
    void retriedRequestsChargeOnce() {
        String concert = createConcert();
        var headers = new HttpHeaders();
        headers.set("Idempotency-Key", "retry-1");
        var body = Map.of("customerId", "gina", "seats", List.of("B4"));
        var first = post(ticketing, "/concerts/" + concert + "/holds", body, headers);
        var second = post(ticketing, "/concerts/" + concert + "/holds", body, headers);
        assertThat(first.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(second.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(second.getBody().get("id")).isEqualTo(first.getBody().get("id"));

        var order = Map.of("holdId", first.getBody().get("id"), "paymentToken", "tok_visa");
        var placed = post(ticketing, "/orders", order);
        var replaced = post(ticketing, "/orders", order);
        assertThat(placed.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(replaced.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(replaced.getBody().get("id")).isEqualTo(placed.getBody().get("id"));
        awaitOrderStatus((String) placed.getBody().get("id"), "CONFIRMED");
    }

    @Test
    void invalidRequestsAreRejected() {
        String concert = createConcert();
        assertThat(post(ticketing, "/concerts/" + concert + "/holds", Map.of("customerId", "h", "seats", List.of("Z9")))
                        .getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(post(ticketing, "/concerts/nope/holds", Map.of("customerId", "h", "seats", List.of("A1")))
                        .getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(post(ticketing, "/orders", Map.of("holdId", "nope", "paymentToken", "tok_visa"))
                        .getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
    }

    /**
     * Once no order awaits a payment outcome, the two databases must agree: money is kept exactly for confirmed
     * orders, and a seat is sold exactly when its order is confirmed.
     */
    @AfterEach
    void invariantsHold() {
        await().atMost(Duration.ofSeconds(30)).until(this::quiet);
        var orders = system.ticketingDb().findAll(Document.class, "orders");
        var payments = system.paymentsDb().findAll(Document.class, "payments").stream()
                .collect(Collectors.toMap(p -> p.getString("_id"), p -> p));
        var soldTo = system.ticketingDb().find(query(where("status").is("SOLD")), Document.class, "seats").stream()
                .collect(Collectors.groupingBy(s -> s.getString("orderId"), Collectors.counting()));

        for (Document order : orders) {
            String id = order.getString("_id");
            String status = order.getString("status");
            var payment = payments.get(id);
            assertThat(payment).as("payment of order %s", id).isNotNull();
            String expectedPayment = switch (status) {
                case "CONFIRMED" -> "CAPTURED";
                case "DECLINED" -> "DECLINED";
                case "REFUNDED" -> "REFUNDED";
                default -> throw new AssertionError("order " + id + " is still " + status);
            };
            assertThat(payment.getString("status")).as("payment of %s order %s", status, id).isEqualTo(expectedPayment);
            long seats = order.getList("seatLabels", String.class).size();
            assertThat(soldTo.getOrDefault(id, 0L)).as("seats sold to %s order %s", status, id)
                    .isEqualTo(status.equals("CONFIRMED") ? seats : 0L);
            if (status.equals("CONFIRMED")) {
                assertThat(payment.getLong("amountCents")).isEqualTo(order.getLong("amountCents"));
            }
        }
        assertThat(payments.keySet()).as("every payment belongs to an order")
                .isSubsetOf(orders.stream().map(o -> o.getString("_id")).toList());
    }

    private boolean quiet() {
        boolean outboxesEmpty = system.ticketingDb().count(query(where("publishedAt").is(null)), "outbox") == 0
                && system.paymentsDb().count(query(where("publishedAt").is(null)), "outbox") == 0;
        boolean noneInFlight = system.ticketingDb()
                        .count(query(where("status").in("PENDING_PAYMENT", "REFUND_PENDING")), "orders")
                == 0;
        return outboxesEmpty && noneInFlight;
    }

    // Helpers

    private static String createConcert() {
        var created = post(
                ticketing,
                "/concerts",
                Map.of(
                        "name", "The Formal Methods",
                        "venue", "Bytecode Hall",
                        "startsAt", Instant.parse("2027-06-01T19:30:00Z").toString(),
                        "priceCents", 4500,
                        "rows", List.of("A", "B"),
                        "seatsPerRow", 5));
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        return (String) created.getBody().get("id");
    }

    private static String hold(String concert, String customer, String... seats) {
        var held = post(
                ticketing, "/concerts/" + concert + "/holds", Map.of("customerId", customer, "seats", List.of(seats)));
        assertThat(held.getStatusCode()).as("hold %s", held.getBody()).isEqualTo(HttpStatus.CREATED);
        return (String) held.getBody().get("id");
    }

    private static String placeOrder(String hold, String token) {
        var placed = post(ticketing, "/orders", Map.of("holdId", hold, "paymentToken", token));
        assertThat(placed.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        return (String) placed.getBody().get("id");
    }

    private static void awaitOrderStatus(String order, String status) {
        await().atMost(BoxOffice.SLOW_PAYMENT.plusSeconds(15))
                .pollInterval(Duration.ofMillis(100))
                .until(() -> get(ticketing, "/orders/" + order).get("status"), status::equals);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, String> seats(String concert) {
        return ((List<Map<String, String>>) get(ticketing, "/concerts/" + concert).get("seats"))
                .stream().collect(Collectors.toMap(s -> s.get("label"), s -> s.get("status")));
    }
}
