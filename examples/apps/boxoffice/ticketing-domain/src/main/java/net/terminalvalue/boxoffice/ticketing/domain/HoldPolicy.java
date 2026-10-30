package net.terminalvalue.boxoffice.ticketing.domain;

import java.time.Duration;
import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;

/**
 * Rules for holding seats: how many one hold may take, how long it lasts, and what it costs.
 *
 * @param maxSeats the most seats one hold may take
 * @param ttl how long a hold lasts. Payment must be captured before then, or the customer is refunded.
 */
public record HoldPolicy(int maxSeats, Duration ttl) {

    public HoldPolicy {
        if (maxSeats < 1) {
            throw new IllegalArgumentException("maxSeats must be positive");
        }
        if (ttl.isNegative() || ttl.isZero()) {
            throw new IllegalArgumentException("ttl must be positive");
        }
    }

    /** Throws {@link IllegalArgumentException} unless the request names 1 to {@code maxSeats} distinct seats. */
    public void validate(List<String> seatLabels) {
        Objects.requireNonNull(seatLabels, "seatLabels");
        if (seatLabels.isEmpty() || seatLabels.size() > maxSeats) {
            throw new IllegalArgumentException("a hold takes between 1 and " + maxSeats + " seats");
        }
        if (new HashSet<>(seatLabels).size() != seatLabels.size()) {
            throw new IllegalArgumentException("seats must be distinct");
        }
    }

    public Instant expiresAt(Instant now) {
        return now.plus(ttl);
    }

    /** A hold of this many seats or more is a group, and gets 10% off. */
    public static final int GROUP_SIZE = 6;

    /**
     * The price of {@code seats} seats: the seat price times the count, less 10% for a group of {@link #GROUP_SIZE}
     * seats or more. The discount is taken off the total and rounded down to the cent. Throws
     * {@link ArithmeticException} rather than overflow.
     */
    public static long totalCents(long priceCents, int seats) {
        if (priceCents < 0 || seats < 0) {
            throw new IllegalArgumentException("price and seat count must not be negative");
        }
        long total = Math.multiplyExact(priceCents, seats);
        return seats >= GROUP_SIZE ? total - total / 10 : total;
    }
}
