package net.terminalvalue.mica.classfile;

import static net.terminalvalue.mica.Tests.equal;

public final class StackMapTableTest {

    private StackMapTableTest() {}

    // javap of a method with a loop: append_frame at 2, chop_frame at 14, same_frame at 20.
    private static final int[] DELTAS = {2, 11, 5};

    public static void theFirstFrameIsAtItsOffsetDelta() {
        equal(2, StackMapTable.offsetOf(DELTAS, 0));
    }

    public static void everyLaterFrameIsOneFurtherThanItsDelta() {
        equal(14, StackMapTable.offsetOf(DELTAS, 1));
        equal(20, StackMapTable.offsetOf(DELTAS, 2));
    }

    public static void consecutiveFramesWithDeltaZeroAreAtConsecutiveOffsets() {
        equal(7, StackMapTable.offsetOf(new int[] {7, 0, 0}, 0));
        equal(8, StackMapTable.offsetOf(new int[] {7, 0, 0}, 1));
        equal(9, StackMapTable.offsetOf(new int[] {7, 0, 0}, 2));
    }
}
