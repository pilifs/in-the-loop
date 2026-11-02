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
 * participants, does what the model says it does. The scenarios cover the paths the model's crash configuration is
 * about: a crash between steps, and one after the coordinator has logged a decision and before the broadcast is
 * out, which the fault injection places after a given I/O operation of a step.
 *
 * <p>Usage: {@code java -cp build/main:build/test net.terminalvalue.quorum.twopc.Traces > spec/TwoPhaseCommitTraces.tla}.
 */
public final class Traces {

    static final List<String> PARTICIPANTS = List.of("p1", "p2", "p3");

    enum Kind { VOTE, GIVE_UP, LEARN, DELIVER, TIMEOUT, CRASH, RECOVER }

    /** One scripted step: what happens, to or from which participant, and after how many I/O operations of the
     * step the coordinator crashes, if it does. */
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
        Script giveUp(String p) { return add(Kind.GIVE_UP, p, null, 0); }
        Script learn(String p) { return add(Kind.LEARN, p, null, 0); }
        Script deliver(String p) { return add(Kind.DELIVER, p, null, 0); }
        Script deliverCrashingAfter(String p, int io) { return add(Kind.DELIVER, p, null, io); }
        Script timeout() { return add(Kind.TIMEOUT, null, null, 0); }
        Script timeoutCrashingAfter(int io) { return add(Kind.TIMEOUT, null, null, io); }
        Script crash() { return add(Kind.CRASH, null, null, 0); }
        Script recover() { return add(Kind.RECOVER, null, null, 0); }
        Script recoverCrashingAfter(int io) { return add(Kind.RECOVER, null, null, io); }

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

    static Run run(Script script) {
        Run run = new Run(script);
        Faults faults = new Faults();
        CoordinatorLog log = new CoordinatorLog(faults);
        Network network = new Network(faults);
        Map<String, ParticipantNode> participants = new TreeMap<>();
        for (String p : PARTICIPANTS) {
            participants.put(p, new ParticipantNode(p, network));
        }
        CoordinatorNode coordinator = new CoordinatorNode(Set.copyOf(PARTICIPANTS), log, network);
        boolean up = true;
        int crashes = 0;
        run.states.add(state(coordinator, log, network, participants, up, crashes));
        for (Step step : script.steps) {
            if (step.crashAfter() > 0) {
                faults.crashAfter(step.crashAfter());
            }
            try {
                switch (step.kind()) {
                    case VOTE -> participants.get(step.participant()).prepare(step.vote() == Vote.YES);
                    case GIVE_UP -> participants.get(step.participant()).giveUp();
                    case LEARN -> participants.get(step.participant()).learn();
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
                up = false;
                crashes++;
            } catch (RuntimeException e) {
                // A rule or the glue threw: the run stops here, and the model's own invariants say what to make of it.
                run.stopped = step + ": " + e;
                break;
            }
            run.states.add(state(coordinator, log, network, participants, up, crashes));
        }
        return run;
    }

    private static void requireUp(boolean up, Step step) {
        if (!up) {
            throw new AssertionError("the coordinator is down: " + step);
        }
    }

    /** The state in the model's variables. The coordinator's phase and tally are what it holds in memory while it
     * is up, and what its log holds while it is down: a restart starts from the log. */
    static String state(CoordinatorNode coordinator, CoordinatorLog log, Network network,
                        Map<String, ParticipantNode> participants, boolean up, int crashes) {
        Phase phase = up ? coordinator.phase() : log.phase();
        Map<String, Vote> tally = up ? coordinator.tally() : log.tally();
        StringBuilder s = new StringBuilder("[phase |-> \"").append(phase).append("\", pstate |-> [");
        s.append(String.join(", ", PARTICIPANTS.stream().map(p -> p + " |-> \"" + participants.get(p).state() + "\"").toList()));
        s.append("], votes |-> [");
        s.append(String.join(", ", PARTICIPANTS.stream().map(p -> p + " |-> \"" + (tally.containsKey(p) ? tally.get(p).name() : "NONE") + "\"").toList()));
        s.append("], inbox |-> {");
        s.append(String.join(", ", network.inFlight().stream().map(m -> "[from |-> \"" + m.from() + "\", vote |-> \"" + m.vote() + "\"]").distinct().toList()));
        s.append("}, decision |-> \"").append(network.decision()).append("\", up |-> ").append(up ? "TRUE" : "FALSE");
        s.append(", crashes |-> ").append(crashes).append("]");
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
