package net.terminalvalue.quorum.replication;

import static net.terminalvalue.quorum.Tests.equal;
import static net.terminalvalue.quorum.replication.LastWriterWins.winner;

public final class LastWriterWinsTest {

    private LastWriterWinsTest() {}

    public static void theLaterTimestampWins() {
        equal(0, winner(200, 1, 100, 2));
        equal(1, winner(100, 1, 200, 2));
    }

    public static void equalTimestampsGoToTheHigherNode() {
        equal(1, winner(100, 1, 100, 2));
        equal(0, winner(100, 2, 100, 1));
    }
}
