package net.terminalvalue.quorum.twopc;

/** What a two-phase-commit coordinator reacts to. */
public sealed interface CoordinatorEvent {

    /**
     * A vote arrived and was counted. {@code complete} says whether every participant has now voted, and
     * {@code unanimous} whether every vote counted so far is yes.
     */
    record Tally(boolean complete, boolean unanimous) implements CoordinatorEvent {}

    /** The vote collection timed out with votes missing; {@code unanimousSoFar} says whether those that came were all yes. */
    record Timeout(boolean unanimousSoFar) implements CoordinatorEvent {}
}
