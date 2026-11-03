package net.terminalvalue.mica.classfile;

import static net.terminalvalue.mica.Tests.equal;

public final class ExceptionTableTest {

    private ExceptionTableTest() {}

    // try { try { ... } catch (A a) {} } catch (B b) {}: javac emits the inner entry first.
    private static final int[] START = {4, 0, 30};
    private static final int[] END = {12, 20, 40};

    public static void anInstructionInsideTheRangeIsCovered() {
        equal(0, ExceptionTable.handlerIndex(START, END, 8));
        equal(2, ExceptionTable.handlerIndex(START, END, 35));
    }

    public static void theFirstEntryInTableOrderWins() {
        equal(0, ExceptionTable.handlerIndex(START, END, 4));
        equal(1, ExceptionTable.handlerIndex(START, END, 2));
        equal(1, ExceptionTable.handlerIndex(START, END, 15));
    }

    public static void anInstructionOutsideEveryRangePropagates() {
        equal(-1, ExceptionTable.handlerIndex(START, END, 25));
        equal(-1, ExceptionTable.handlerIndex(START, END, 44));
        equal(-1, ExceptionTable.handlerIndex(new int[0], new int[0], 0));
    }

    public static void theStartIsCoveredAndTheEndIsNot() {
        equal(2, ExceptionTable.handlerIndex(START, END, 30));
        equal(-1, ExceptionTable.handlerIndex(START, END, 41));
    }

    // The entries javac emits for the nested try above, in a method of 48 bytes.
    public static void wellFormedEntriesAreAccepted() {
        ExceptionTable.checkEntry(4, 12, 15, 48);
        ExceptionTable.checkEntry(0, 20, 23, 48);
        ExceptionTable.checkEntry(30, 40, 43, 48);
    }

    public static void anEmptyOrInvertedRangeIsRejected() {
        throwsClassFormat(() -> ExceptionTable.checkEntry(12, 12, 15, 48));
        throwsClassFormat(() -> ExceptionTable.checkEntry(12, 4, 15, 48));
    }

    public static void aRangeOrHandlerOutsideTheCodeIsRejected() {
        throwsClassFormat(() -> ExceptionTable.checkEntry(30, 49, 43, 48));
        throwsClassFormat(() -> ExceptionTable.checkEntry(30, 40, 48, 48));
    }

    private static void throwsClassFormat(Runnable action) {
        try {
            action.run();
        } catch (ClassFormatError e) {
            return;
        }
        throw new AssertionError("expected ClassFormatError");
    }
}
