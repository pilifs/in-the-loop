package net.terminalvalue.boxoffice.ticketing.api;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.PositiveOrZero;
import java.net.URI;
import java.time.Instant;
import java.util.List;
import net.terminalvalue.boxoffice.ticketing.app.ConcertService;
import net.terminalvalue.boxoffice.ticketing.app.HoldService;
import net.terminalvalue.boxoffice.ticketing.domain.SeatStatus;
import net.terminalvalue.boxoffice.ticketing.store.ConcertDocument;
import net.terminalvalue.boxoffice.ticketing.store.HoldDocument;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Synchronous capabilities: create a concert, see which seats are free, and hold seats. */
@RestController
@RequestMapping("/concerts")
class ConcertController {

    record CreateConcert(
            @NotBlank String name,
            @NotBlank String venue,
            @NotNull Instant startsAt,
            @PositiveOrZero long priceCents,
            @NotEmpty List<@Pattern(regexp = "[A-Z]") String> rows,
            @Min(1) @Max(50) int seatsPerRow) {}

    record Seat(String label, SeatStatus status) {}

    record Concert(String id, String name, String venue, Instant startsAt, long priceCents, List<Seat> seats) {}

    record HoldSeats(@NotBlank String customerId, @NotEmpty List<@NotBlank String> seats) {}

    record Hold(String id, String concertId, List<String> seats, String customerId, long amountCents, Instant expiresAt) {
        static Hold of(HoldDocument hold) {
            return new Hold(
                    hold.id(), hold.concertId(), hold.seatLabels(), hold.customerId(), hold.amountCents(), hold.expiresAt());
        }
    }

    private final ConcertService concerts;
    private final HoldService holds;

    ConcertController(ConcertService concerts, HoldService holds) {
        this.concerts = concerts;
        this.holds = holds;
    }

    @PostMapping
    ResponseEntity<Concert> create(@Valid @RequestBody CreateConcert request) {
        ConcertDocument concert = concerts.create(
                request.name(), request.venue(), request.startsAt(), request.priceCents(), request.rows(), request.seatsPerRow());
        return ResponseEntity.created(URI.create("/concerts/" + concert.id())).body(get(concert.id()));
    }

    @GetMapping("/{id}")
    Concert get(@PathVariable String id) {
        var availability = concerts.availability(id);
        var concert = availability.concert();
        return new Concert(
                concert.id(),
                concert.name(),
                concert.venue(),
                concert.startsAt(),
                concert.priceCents(),
                availability.seats().stream().map(s -> new Seat(s.label(), s.status())).toList());
    }

    /**
     * Holds seats for {@code holdTtl}. Responds 201 with the hold, 409 if any seat is taken, or 200 with the earlier
     * hold if the {@code Idempotency-Key} was used before.
     */
    @PostMapping("/{id}/holds")
    ResponseEntity<Hold> hold(
            @PathVariable String id,
            @RequestHeader(name = "Idempotency-Key", required = false) String idempotencyKey,
            @Valid @RequestBody HoldSeats request) {
        var result = holds.hold(id, request.customerId(), request.seats(), idempotencyKey);
        var body = Hold.of(result.value());
        return result.created()
                ? ResponseEntity.created(URI.create("/holds/" + body.id())).body(body)
                : ResponseEntity.status(HttpStatus.OK).body(body);
    }
}
