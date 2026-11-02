package net.terminalvalue.quorum.clock;

/**
 * A hybrid logical clock (Kulkarni et al., 2014): a timestamp that tracks physical time closely and still orders
 * every causally related pair of events, as CockroachDB and YugabyteDB use for transaction ordering.
 *
 * <p>A timestamp is one {@code long}: the physical part (milliseconds, 47 bits) in the high bits and a logical
 * counter (16 bits) in the low bits, so that comparing timestamps is comparing longs. The two rules are:
 *
 * <ul>
 *   <li>{@link #tick}: a local or send event takes the physical clock if it moved past the last timestamp, else the
 *       last timestamp with the counter incremented.
 *   <li>{@link #receive}: a receive event takes the largest physical part of the local clock, the last timestamp
 *       and the message; the counter continues from whichever of the two timestamps had that physical part, or
 *       from the larger counter when both did, or restarts at zero when the physical clock won.
 * </ul>
 *
 * The property this buys: the result of either rule is greater than every timestamp it saw.
 */
public final class HybridLogicalClock {

    public static final int LOGICAL_BITS = 16;
    public static final long LOGICAL_MASK = (1L << LOGICAL_BITS) - 1;
    /** The largest physical part: 47 bits, so that a timestamp is never negative. */
    public static final long MAX_PHYSICAL = (1L << (63 - LOGICAL_BITS)) - 1;

    private HybridLogicalClock() {}

    public static long physical(long timestamp) {
        return timestamp >>> LOGICAL_BITS;
    }

    public static int logical(long timestamp) {
        return (int) (timestamp & LOGICAL_MASK);
    }

    /** A timestamp from its parts. The counter has 16 bits; exhausting them is a fault, not a wrap-around. */
    public static long of(long physical, long logical) {
        if (physical < 0 || physical > MAX_PHYSICAL) {
            throw new IllegalArgumentException("physical time out of range");
        }
        if (logical < 0 || logical > LOGICAL_MASK) {
            throw new IllegalStateException("logical counter exhausted");
        }
        return (physical << LOGICAL_BITS) | logical;
    }

    /** The timestamp of a local or send event. */
    public static long tick(long nowMillis, long last) {
        if (nowMillis > physical(last)) {
            return of(nowMillis, 0);
        }
        return of(physical(last), logical(last) + 1L);
    }

    /** The timestamp of a receive event, given the message's timestamp. */
    public static long receive(long nowMillis, long last, long message) {
        long lastPhysical = physical(last);
        long messagePhysical = physical(message);
        if (nowMillis > lastPhysical && nowMillis > messagePhysical) {
            return of(nowMillis, 0);
        }
        if (lastPhysical == messagePhysical) {
            return of(lastPhysical, Math.max(logical(last), logical(message)) + 1L);
        }
        if (lastPhysical > messagePhysical) {
            return of(lastPhysical, logical(last) + 1L);
        }
        return of(messagePhysical, logical(message) + 1L);
    }
}
