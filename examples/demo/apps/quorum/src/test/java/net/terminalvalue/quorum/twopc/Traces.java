package net.terminalvalue.quorum.twopc;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/**
 * Trace validation: runs the two-phase-commit nodes through scripted scenarios and prints the state after each step
 * as a TLA+ module, {@code TwoPhaseCommitTraces.tla}, in the variables of the model {@code TwoPhaseCommit.tla}.
 * {@code TwoPhaseCommitTrace.tla} then has TLC walk each recorded run and check that every step is a step of the
 * model's next-state relation: that the glue around the verified decision rules, the log, the broadcast and the
 * participants, does what the model says it does. The scenarios cover the paths the model's crash configurations
 * are about: a crash between steps, one after the coordinator has logged a decision and before the broadcast is
 * out, and one after a participant has logged its vote and before the vote is sent, which the fault injection
 * places after a given I/O operation of a step.
 *
 * <p>Usage: {@code java -cp build/main:build/test net.terminalvalue.quorum.twopc.Traces > spec/TwoPhaseCommitTraces.tla}.
 */
public final class Traces {

    static final List<String> PARTICIPANTS = List.of("p1", "p2", "p3");

    enum Kind { VOTE, GIVE_UP, LEARN, DELIVER, TIMEOUT, CRASH, RECOVER, PARTICIPANT_CRASH, PARTICIPANT_RECOVER }

    /** One scripted step: what happens, to or from which participant, and after how many I/O operations of the
     * step the process taking it crashes, if it does: the participant for a vote, the coordinator otherwise. */
    record Step(Kind kind, String participant, Vote vote, int crashAfter) {
        @Override
        public String toString() {
            String what = switch (kind) {
                case VOTE -> participant + " votes " + vote.name().toLowerCase();
                case GIVE_UP -> participant + " gives up";
                case LEARN -> participant + " learns the decision";
                case DELIVER -> "the coordinator receives " + participant + "'s vote";
                case TIMEOUT -> "the coordinator's timer fires";
                case CRASH -> "the coordinator crashes";
                case RECOVER -> "the coordinator restarts";
                case PARTICIPANT_CRASH -> participant + " crashes";
                case PARTICIPANT_RECOVER -> participant + " restarts";
            };
            return crashAfter > 0 ? what + " and crashes after its " + (crashAfter == 1 ? "first" : crashAfter + "th") + " I/O operation" : what;
        }
    }

    /** A scenario: a name and the steps, in order. */
    static final class Script {
        final String name;
        final List<Step> steps = new ArrayList<>();

        Script(String name) {
            this.name = name;
        }

        Script vote(String p, Vote v) { return add(Kind.VOTE, p, v, 0); }
        Script voteCrashingAfter(String p, Vote v, int io) { return add(Kind.VOTE, p, v, io); }
        Script giveUp(String p) { return add(Kind.GIVE_UP, p, null, 0); }
        Script learn(String p) { return add(Kind.LEARN, p, null, 0); }
        Script deliver(String p) { return add(Kind.DELIVER, p, null, 0); }
        Script deliverCrashingAfter(String p, int io) { return add(Kind.DELIVER, p, null, io); }
        Script timeout() { return add(Kind.TIMEOUT, null, null, 0); }
        Script timeoutCrashingAfter(int io) { return add(Kind.TIMEOUT, null, null, io); }
        Script crash() { return add(Kind.CRASH, null, null, 0); }
        Script recover() { return add(Kind.RECOVER, null, null, 0); }
        Script recoverCrashingAfter(int io) { return add(Kind.RECOVER, null, null, io); }
        Script crash(String p) { return add(Kind.PARTICIPANT_CRASH, p, null, 0); }
        Script recover(String p) { return add(Kind.PARTICIPANT_RECOVER, p, null, 0); }

        private Script add(Kind kind, String p, Vote v, int io) {
            steps.add(new Step(kind, p, v, io));
            return this;
        }
    }

    /** The scenarios, each a run of the protocol from the initial state. */
    static List<Script> scripts() {
        return List.of(
                new Script("every participant votes yes, and the coordinator commits")
                        .vote("p1", Vote.YES).vote("p2", Vote.YES).vote("p3", Vote.YES)
                        .deliver("p1").deliver("p2").deliver("p3")
                        .learn("p1").learn("p2").learn("p3"),
                new Script("one participant votes no, and the coordinator aborts once every vote is in")
                        .vote("p1", Vote.YES).vote("p2", Vote.NO)
                        .deliver("p2").deliver("p1")
                        .vote("p3", Vote.YES).deliver("p3")
                        .learn("p1").learn("p3"),
                new Script("a vote is late, and the coordinator aborts on its timer")
                        .vote("p1", Vote.YES).deliver("p1").vote("p2", Vote.YES)
                        .timeout()
                        .deliver("p2").learn("p1").learn("p2").learn("p3"),
                new Script("a participant gives up without voting, and the coordinator aborts on its timer")
                        .giveUp("p1").vote("p2", Vote.YES).deliver("p2")
                        .timeout()
                        .learn("p2").learn("p3"),
                new Script("the coordinator crashes while collecting, and restarts with the presumed abort")
                        .vote("p1", Vote.YES).deliver("p1")
                        .crash()
                        .vote("p2", Vote.YES)
                        .recover()
                        .deliver("p2").learn("p1").learn("p2").learn("p3"),
                new Script("the coordinator crashes after logging the commit and before the broadcast, and restarts")
                        .vote("p1", Vote.YES).vote("p2", Vote.YES).vote("p3", Vote.YES)
                        .deliver("p1").deliver("p2")
                        .deliverCrashingAfter("p3", 1)
                        .recover()
                        .learn("p1").learn("p2").learn("p3"),
                new Script("the coordinator crashes after logging the abort its timer decided, and restarts")
                        .vote("p1", Vote.YES).deliver("p1")
                        .timeoutCrashingAfter(1)
                        .recover()
                        .learn("p1").vote("p2", Vote.NO).deliver("p2").learn("p3"),
                new Script("a restart is itself cut short by a crash, and the next one finishes it")
                        .vote("p1", Vote.YES).deliver("p1")
                        .crash()
                        .recoverCrashingAfter(1)
                        .recover()
                        .learn("p1").learn("p2").learn("p3"),
                new Script("a participant crashes after voting yes, restarts holding its locks, and learns the decision")
                        .vote("p1", Vote.YES).deliver("p1")
                        .crash("p1")
                        .vote("p2", Vote.YES).vote("p3", Vote.YES).deliver("p2").deliver("p3")
                        .recover("p1")
                        .learn("p1").learn("p2").learn("p3"),
                new Script("a participant crashes before voting, restarts aborted, and the coordinator aborts on its timer")
                        .crash("p1")
                        .vote("p2", Vote.YES).deliver("p2")
                        .recover("p1")
                        .timeout()
                        .learn("p2").learn("p3"),
                new Script("a participant crashes after logging its yes and before sending it, and the timer aborts")
                        .voteCrashingAfter("p1", Vote.YES, 1)
                        .vote("p2", Vote.YES).deliver("p2")
                        .recover("p1")
                        .timeout()
                        .learn("p1").learn("p2").learn("p3"));
    }

    /** The recorded run of one scenario: the state after the initial step and after each scripted one, as TLA+
     * records in the model's variables, and the step at which the run stopped early, if it did. */
    static final class Run {
        final Script script;
        final List<String> states = new ArrayList<>();
        String stopped;

        Run(Script script) {
            this.script = script;
        }
    }

    /** A participant process with its log and its fault injection, up or crashed. */
    static final class Participant {
        final String name;
        final Faults faults;
        final ParticipantLog log;
        ParticipantNode node;
        boolean up = true;

        Participant(String name, Network network) {
            this.name = name;
            this.faults = new Faults(name);
            this.log = new ParticipantLog(faults);
            this.node = new ParticipantNode(name, log, network, faults);
        }

        /** The participant's state: what it holds in memory while it is up, and what its log holds while it is down. */
        ParticipantState state() {
            return up ? node.state() : log.state();
        }
    }

    static Run run(Script script) {
        Run run = new Run(script);
        Faults faults = new Faults();
        CoordinatorLog log = new CoordinatorLog(faults);
        Network network = new Network(faults);
        Map<String, Participant> participants = new TreeMap<>();
        for (String p : PARTICIPANTS) {
            participants.put(p, new Participant(p, network));
        }
        CoordinatorNode coordinator = new CoordinatorNode(Set.copyOf(PARTICIPANTS), log, network);
        boolean up = true;
        int crashes = 0;
        int participantCrashes = 0;
        run.states.add(state(coordinator, log, network, participants, up, crashes, participantCrashes));
        for (Step step : script.steps) {
            boolean participantStep = step.kind() == Kind.VOTE || step.kind() == Kind.GIVE_UP || step.kind() == Kind.LEARN;
            Participant participant = step.participant() == null ? null : participants.get(step.participant());
            if (step.crashAfter() > 0) {
                (participantStep ? participant.faults : faults).crashAfter(step.crashAfter());
            }
            try {
                switch (step.kind()) {
                    case VOTE -> requireUp(participant, step).prepare(step.vote() == Vote.YES);
                    case GIVE_UP -> requireUp(participant, step).giveUp();
                    case LEARN -> requireUp(participant, step).learn();
                    case PARTICIPANT_CRASH -> {
                        requireUp(participant, step);
                        participant.up = false;
                        participantCrashes++;
                    }
                    case PARTICIPANT_RECOVER -> {
                        if (participant.up) {
                            throw new AssertionError(participant.name + " is up: " + step);
                        }
                        participant.node = new ParticipantNode(participant.name, participant.log, network, participant.faults);
                        participant.up = true;
                        participant.node.recover();
                    }
                    case DELIVER -> {
                        requireUp(up, step);
                        coordinator.onVote(network.deliver(step.participant()));
                    }
                    case TIMEOUT -> {
                        requireUp(up, step);
                        coordinator.onTimeout();
                    }
                    case CRASH -> {
                        requireUp(up, step);
                        up = false;
                        crashes++;
                    }
                    case RECOVER -> {
                        if (up) {
                            throw new AssertionError("the coordinator is up: " + step);
                        }
                        coordinator = new CoordinatorNode(Set.copyOf(PARTICIPANTS), log, network);
                        up = true;
                        coordinator.recover();
                    }
                }
            } catch (Faults.Crashed e) {
                if (participantStep) {
                    participant.up = false;
                    participantCrashes++;
                } else {
                    up = false;
                    crashes++;
                }
            } catch (RuntimeException e) {
                // A rule or the glue threw: the run stops here, and the model's own invariants say what to make of it.
                run.stopped = step + ": " + e;
                break;
            }
            run.states.add(state(coordinator, log, network, participants, up, crashes, participantCrashes));
        }
        return run;
    }

    private static void requireUp(boolean up, Step step) {
        if (!up) {
            throw new AssertionError("the coordinator is down: " + step);
        }
    }

    private static ParticipantNode requireUp(Participant participant, Step step) {
        if (!participant.up) {
            throw new AssertionError(participant.name + " is down: " + step);
        }
        return participant.node;
    }

    /** The state in the model's variables. A process's state is what it holds in memory while it is up, and what
     * its log holds while it is down: a restart starts from the log. */
    static String state(CoordinatorNode coordinator, CoordinatorLog log, Network network,
                        Map<String, Participant> participants, boolean up, int crashes, int participantCrashes) {
        Phase phase = up ? coordinator.phase() : log.phase();
        Map<String, Vote> tally = up ? coordinator.tally() : log.tally();
        StringBuilder s = new StringBuilder("[phase |-> \"").append(phase).append("\", pstate |-> [");
        s.append(String.join(", ", PARTICIPANTS.stream().map(p -> p + " |-> \"" + participants.get(p).state() + "\"").toList()));
        s.append("], votes |-> [");
        s.append(String.join(", ", PARTICIPANTS.stream().map(p -> p + " |-> \"" + (tally.containsKey(p) ? tally.get(p).name() : "NONE") + "\"").toList()));
        s.append("], inbox |-> {");
        s.append(String.join(", ", network.inFlight().stream().map(m -> "[from |-> \"" + m.from() + "\", vote |-> \"" + m.vote() + "\"]").distinct().toList()));
        s.append("}, decision |-> \"").append(network.decision()).append("\", up |-> ").append(up ? "TRUE" : "FALSE");
        s.append(", crashes |-> ").append(crashes).append(", pup |-> [");
        s.append(String.join(", ", PARTICIPANTS.stream().map(p -> p + " |-> " + (participants.get(p).up ? "TRUE" : "FALSE")).toList()));
        s.append("], pcrashes |-> ").append(participantCrashes).append("]");
        return s.toString();
    }

    static String module(List<Run> runs) {
        StringBuilder out = new StringBuilder();
        out.append("---------------------------- MODULE TwoPhaseCommitTraces ----------------------------\n");
        out.append("(* The recorded runs of the Java nodes of two-phase commit, one state per step in the model's   *)\n");
        out.append("(* variables, generated by net.terminalvalue.quorum.twopc.Traces from its scripted scenarios.   *)\n");
        out.append("(* TwoPhaseCommitTrace.tla checks each against the model. Do not edit: regenerate it with       *)\n");
        out.append("(* java -cp build/main:build/test net.terminalvalue.quorum.twopc.Traces > spec/TwoPhaseCommitTraces.tla *)\n");
        out.append("EXTENDS Sequences\n\n");
        out.append("Names == <<\n");
        for (int i = 0; i < runs.size(); i++) {
            out.append("    \"").append(runs.get(i).script.name).append('"').append(i + 1 < runs.size() ? ",\n" : "\n");
        }
        out.append(">>\n\nTraces == <<\n");
        for (int i = 0; i < runs.size(); i++) {
            Run run = runs.get(i);
            out.append("    \\* ").append(i + 1).append(". ").append(run.script.name).append('\n');
            out.append("    <<\n");
            for (int k = 0; k < run.states.size(); k++) {
                out.append("        \\* ").append(k == 0 ? "the initial state" : run.script.steps.get(k - 1).toString()).append('\n');
                out.append("        ").append(run.states.get(k)).append(k + 1 < run.states.size() ? ",\n" : "\n");
            }
            if (run.stopped != null) {
                out.append("        \\* stopped early, at ").append(run.stopped).append('\n');
            }
            out.append("    >>").append(i + 1 < runs.size() ? ",\n" : "\n");
        }
        out.append(">>\n\n");
        out.append("=============================================================================\n");
        return out.toString();
    }

    public static void main(String[] args) {
        List<Run> runs = scripts().stream().map(Traces::run).toList();
        System.out.print(module(runs));
        for (Run run : runs) {
            if (run.stopped != null) {
                System.err.println("stopped early: " + run.script.name + ", at " + run.stopped);
            }
        }
    }
}
