package net.terminalvalue.mica.classfile;

/**
 * The exception table of a {@code Code} attribute (JVMS §4.7.3). An entry covers the instructions whose pc lies in
 * the half-open range {@code [start_pc, end_pc)}, and when an instruction throws, the first entry in table order
 * that covers its pc is taken (JVMS §2.10): javac relies on the order to put an inner handler before the outer one
 * it is nested in. The specification calls the exclusive {@code end_pc} a historical mistake in the design of the
 * virtual machine, and keeps it, because every class file ever compiled depends on it.
 */
public final class ExceptionTable {

    private ExceptionTable() {}

    /**
     * Checks an entry as the class file reader does (JVMS §4.7.3): {@code start_pc} is before {@code end_pc},
     * {@code end_pc} is at most {@code code_length} (the range is half-open, so a handler may cover the last
     * instruction by ending at the end of the code), and {@code handler_pc} is inside the code. An entry that
     * fails is a {@code ClassFormatError}: the class file is malformed, and the method is never run.
     */
    public static void checkEntry(int startPc, int endPc, int handlerPc, int codeLength) {
        if (startPc >= endPc || endPc > codeLength || handlerPc >= codeLength) {
            throw new ClassFormatError("Illegal exception table range in class file");
        }
    }

    /**
     * The index of the entry that handles an exception thrown by the instruction at {@code pc}, or -1 when no entry
     * covers it and the exception propagates to the caller. The catch type is matched by the caller of this method,
     * which has the constant pool; {@code startPc} and {@code endPc} are the columns of the table, in table order.
     */
    public static int handlerIndex(int[] startPc, int[] endPc, int pc) {
        for (int i = 0; i < startPc.length; i++) {
            if (startPc[i] <= pc && pc < endPc[i]) {
                return i;
            }
        }
        return -1;
    }
}
