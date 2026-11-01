package fixtures;

/** Methods that throw by design, for properties with throws clauses. */
public final class Checks {

    private Checks() {}

    /**
     * The bytes an exception table entry protects, after the checks of JVMS §4.7.3: {@code start_pc < end_pc},
     * {@code end_pc <= code_length} and {@code handler_pc < code_length}; a {@code ClassFormatError} otherwise,
     * which JBMC has no model of.
     */
    public static int protectedLength(int startPc, int endPc, int handlerPc, int codeLength) {
        if (startPc >= endPc || endPc > codeLength || handlerPc >= codeLength) {
            throw new ClassFormatError("Illegal exception table range");
        }
        return endPc - startPc;
    }

    /** Rejects a negative count, and (a bug) zero as well. */
    public static void count(int n) {
        if (n <= 0) {
            throw new IllegalArgumentException("negative");
        }
    }
}
