package net.terminalvalue.mica.asm;

/**
 * The {@code max_stack} of a {@code Code} attribute (JVMS §4.7.3): the deepest the operand stack gets at any point
 * during execution, which the assembler computes from the stack effect of each instruction. A straight-line
 * sequence starts with an empty stack, so the depth after instruction {@code i} is the sum of the first
 * {@code i + 1} effects, and {@code max_stack} is the largest of those depths, or 0.
 */
public final class MaxStack {

    private MaxStack() {}

    /** The {@code max_stack} of a straight-line sequence whose instructions change the depth by {@code delta}. */
    public static int of(int[] delta) {
        int depth = 0;
        int max = 0;
        for (int i = 0; i < delta.length; i++) {
            depth += delta[i];
            if (depth > max) {
                max = depth;
            }
        }
        return max;
    }
}
