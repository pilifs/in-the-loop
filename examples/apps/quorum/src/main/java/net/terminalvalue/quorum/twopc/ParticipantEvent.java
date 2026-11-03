package net.terminalvalue.quorum.twopc;

/** What a two-phase-commit participant reacts to. */
public sealed interface ParticipantEvent {

    /** The coordinator asks the participant to prepare; {@code able} says whether it can do its part. */
    record Prepare(boolean able) implements ParticipantEvent {}

    /** The participant's own timer fires while it waits to be asked: it may give up on the transaction. */
    record GiveUp() implements ParticipantEvent {}

    /** The participant reads the coordinator's broadcast: the decision, or none yet. */
    record Learned(Outcome outcome) implements ParticipantEvent {}

    /** The participant restarted after a crash, with the state it last logged and nothing else. */
    record Restarted() implements ParticipantEvent {}
}
