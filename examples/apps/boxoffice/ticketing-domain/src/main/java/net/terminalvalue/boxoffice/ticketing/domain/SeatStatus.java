package net.terminalvalue.boxoffice.ticketing.domain;

import java.time.Instant;

/**
 * The status of one seat. A held seat records its hold and when the hold expires, and a sold seat records its order.
 *
 * <pre>
 * AVAILABLE --hold--> HELD --sell--> SOLD --release (cancellation)--> AVAILABLE
 *                      \--release (expiry or decline)--> AVAILABLE
 * </pre>
 */
public enum SeatStatus {
    AVAILABLE,
    HELD,
    SOLD;

    /**
     * Whether a new hold may take the seat. A held seat whose hold has expired is free even before the sweeper
     * releases it. The store's conditional update encodes the same predicate, which is what makes it atomic.
     */
    public static boolean isHoldable(SeatStatus status, Instant holdExpiresAt, Instant now) {
        return switch (status) {
            case AVAILABLE -> true;
            case HELD -> !holdExpiresAt.isAfter(now);
            case SOLD -> false;
        };
    }
}
