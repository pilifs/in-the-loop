package net.terminalvalue.quorum.clock;

import static net.terminalvalue.quorum.Tests.check;
import static net.terminalvalue.quorum.Tests.equal;
import static net.terminalvalue.quorum.clock.HybridLogicalClock.logical;
import static net.terminalvalue.quorum.clock.HybridLogicalClock.of;
import static net.terminalvalue.quorum.clock.HybridLogicalClock.physical;
import static net.terminalvalue.quorum.clock.HybridLogicalClock.receive;
import static net.terminalvalue.quorum.clock.HybridLogicalClock.tick;

public final class HybridLogicalClockTest {

    private HybridLogicalClockTest() {}

    public static void partsRoundTrip() {
        long ts = of(1_700_000_000_000L, 42);
        equal(1_700_000_000_000L, physical(ts));
        equal(42, logical(ts));
    }

    public static void tickFollowsThePhysicalClockWhenItMoved() {
        equal(of(1001, 0), tick(1001, of(1000, 7)));
    }

    public static void tickCountsWhenThePhysicalClockStoodStillOrWentBack() {
        equal(of(1000, 8), tick(1000, of(1000, 7)));
        equal(of(1000, 8), tick(990, of(1000, 7)));
    }

    public static void receiveTakesThePhysicalClockWhenItIsAhead() {
        equal(of(1005, 0), receive(1005, of(1000, 7), of(1003, 2)));
    }

    public static void receiveContinuesTheMessageWhenItIsAhead() {
        equal(of(1003, 3), receive(1000, of(1000, 7), of(1003, 2)));
    }

    public static void receiveContinuesTheLargerCounterOnEqualPhysicalParts() {
        equal(of(1003, 10), receive(1000, of(1003, 4), of(1003, 9)));
        equal(of(1003, 10), receive(1000, of(1003, 9), of(1003, 4)));
    }

    public static void timestampsOrderAsLongs() {
        check(of(1000, 65535) < of(1001, 0), "a later millisecond beats any counter");
        check(of(1000, 1) < of(1000, 2), "the counter orders within a millisecond");
    }
}
