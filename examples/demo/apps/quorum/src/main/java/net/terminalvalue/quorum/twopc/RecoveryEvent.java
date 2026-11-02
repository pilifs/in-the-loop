package net.terminalvalue.quorum.twopc;

/** What a two-phase-commit coordinator's recovery rule reacts to. */
public sealed interface RecoveryEvent {

    /** The coordinator restarted after a crash, with the phase it last logged and nothing else. */
    record Restarted() implements RecoveryEvent {}
}
