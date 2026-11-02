package net.terminalvalue.boxoffice.ticketing.api;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.net.URI;
import java.time.Instant;
import java.util.List;
import net.terminalvalue.boxoffice.ticketing.app.OrderService;
import net.terminalvalue.boxoffice.ticketing.domain.OrderStatus;
import net.terminalvalue.boxoffice.ticketing.store.OrderDocument;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Asynchronous capabilities: placing and cancelling an order answer 202 Accepted, and the client polls
 * {@code GET /orders/{id}} until the payment service has answered.
 */
@RestController
@RequestMapping("/orders")
class OrderController {

    record PlaceOrder(@NotBlank String holdId, @NotBlank String paymentToken) {}

    record Order(
            String id,
            String holdId,
            String concertId,
            List<String> seats,
            String customerId,
            long amountCents,
            OrderStatus status,
            Instant createdAt,
            Instant updatedAt) {
        static Order of(OrderDocument o) {
            return new Order(
                    o.id(), o.holdId(), o.concertId(), o.seatLabels(), o.customerId(), o.amountCents(), o.status(),
                    o.createdAt(), o.updatedAt());
        }
    }

    private final OrderService orders;

    OrderController(OrderService orders) {
        this.orders = orders;
    }

    /** Responds 202 with a new order, 200 with the existing one for this hold, or 409 if the hold has expired. */
    @PostMapping
    ResponseEntity<Order> place(@Valid @RequestBody PlaceOrder request) {
        var result = orders.place(request.holdId(), request.paymentToken());
        var body = Order.of(result.value());
        return ResponseEntity.status(result.created() ? HttpStatus.ACCEPTED : HttpStatus.OK)
                .location(URI.create("/orders/" + body.id()))
                .body(body);
    }

    @GetMapping("/{id}")
    Order get(@PathVariable String id) {
        return Order.of(orders.get(id));
    }

    /** Responds 202 once the cancellation is recorded; the order becomes REFUNDED when the refund completes. */
    @PostMapping("/{id}/cancellation")
    ResponseEntity<Order> cancel(@PathVariable String id) {
        return ResponseEntity.accepted().body(Order.of(orders.cancel(id)));
    }
}
