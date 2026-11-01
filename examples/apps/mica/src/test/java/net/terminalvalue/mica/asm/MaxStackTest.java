package net.terminalvalue.mica.asm;

import static net.terminalvalue.mica.Tests.equal;

public final class MaxStackTest {

    private MaxStackTest() {}

    // iload, iload, iadd, ireturn: two pushes, a binary operation, a return.
    public static void anAdditionNeedsTwoSlots() {
        equal(2, MaxStack.of(new int[] {1, 1, -1, -1}));
    }

    // lload, lload, ladd, lreturn: longs take two slots each.
    public static void longsTakeTwoSlotsEach() {
        equal(4, MaxStack.of(new int[] {2, 2, -2, -2}));
    }

    public static void anEmptyMethodNeedsNone() {
        equal(0, MaxStack.of(new int[] {0}));
        equal(0, MaxStack.of(new int[0]));
    }

    // invokestatic of a void method after two pushes, then a push and return: the deepest point is early.
    public static void theDeepestPointNeedNotBeTheLast() {
        equal(2, MaxStack.of(new int[] {1, 1, -2, 1, -1}));
    }
}
