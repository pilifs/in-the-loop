package net.terminalvalue.crosscut.kafka;

import static net.terminalvalue.crosscut.Tests.check;
import static net.terminalvalue.crosscut.Tests.equal;
import static net.terminalvalue.crosscut.Tests.throwsIllegalArgument;

public final class PartitionerTest {

    private PartitionerTest() {}

    public static void spreadsHashesOverThePartitions() {
        equal(0, Partitioner.partitionFor(0, 12));
        equal(7, Partitioner.partitionFor(7, 12));
        equal(1, Partitioner.partitionFor(13, 12));
    }

    public static void negativeHashesLandOnAPartition() {
        for (int hash : new int[] {-1, -17, -123_456_789}) {
            int partition = Partitioner.partitionFor(hash, 12);
            check(partition >= 0 && partition < 12, "partition " + partition + " for hash " + hash);
        }
    }

    public static void refusesATopicWithoutPartitions() {
        throwsIllegalArgument(() -> Partitioner.partitionFor(7, 0));
    }
}
