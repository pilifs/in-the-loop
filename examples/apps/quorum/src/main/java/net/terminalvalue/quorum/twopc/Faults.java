package net.terminalvalue.quorum.twopc;

/**
 * Fault injection for one process's I/O: the coordinator's, or a participant's. The process's log and its sends
 * report each operation here once it has taken effect; a scripted crash is thrown after the operation it was
 * scheduled for, so that a run can lose the process between any two I/O operations, which is where a real crash
 * falls.
 */
public final class Faults {

    /** The process died: whatever it had not yet written or sent is lost, its log is not. */
    public static final class Crashed extends RuntimeException {
        Crashed(String process) {
            super(process + " crashed");
        }
    }

    private final String process;
    private int operationsLeft = -1;

    /** The coordinator's faults. */
    public Faults() {
        this("the coordinator");
    }

    /** The faults of the named process. */
    public Faults(String process) {
        this.process = process;
    }

    /** Schedules a crash right after the next {@code operations} I/O operations; 1 is after the very next one. */
    public void crashAfter(int operations) {
        if (operations < 1) {
            throw new IllegalArgumentException("a crash comes after at least one operation");
        }
        operationsLeft = operations;
    }

    /** An I/O operation has taken effect. */
    public void io() {
        if (operationsLeft > 0 && --operationsLeft == 0) {
            operationsLeft = -1;
            throw new Crashed(process);
        }
    }
}
