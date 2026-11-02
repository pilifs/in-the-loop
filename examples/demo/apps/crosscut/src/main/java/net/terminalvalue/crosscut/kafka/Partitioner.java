package net.terminalvalue.crosscut.kafka;

/**
 * The arithmetic of a key-based partitioner: a key's hash, which may be any {@code int}, to a partition number in
 * {@code [0, numPartitions)}. Every record of a key must land on the same partition for ordering to hold, so this
 * function is what a consumer's ordering guarantee rests on.
 */
public final class Partitioner {

    private Partitioner() {}

    /** Kafka's {@code Utils.toPositive(hash) % numPartitions}: clear the sign bit, then take the remainder. */
    public static int partitionFor(int hash, int numPartitions) {
        if (numPartitions <= 0) {
            throw new IllegalArgumentException("a topic has at least one partition");
        }
        return (hash & 0x7fffffff) % numPartitions;
    }
}
