package net.terminalvalue.mica.classfile;

import static net.terminalvalue.mica.Tests.equal;

public final class ConstantPoolTest {

    private ConstantPoolTest() {}

    // javap -v of a class with a long constant: #1 Methodref, #2 Long, #4 Class, #5 Utf8.
    private static final byte[] TAGS = {10, 5, 7, 1};

    public static void entriesAreNumberedFromOne() {
        equal(1, ConstantPool.indexOf(TAGS, 0));
        equal(1, ConstantPool.indexOf(new byte[] {1}, 0));
    }

    public static void theEntryAfterALongSkipsANumber() {
        equal(4, ConstantPool.indexOf(TAGS, 2));
        equal(5, ConstantPool.indexOf(TAGS, 3));
    }

    public static void aDoubleTakesTwoNumbersAsWell() {
        equal(5, ConstantPool.indexOf(new byte[] {6, 6, 1}, 2));
    }
}
