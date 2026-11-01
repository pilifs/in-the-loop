package net.terminalvalue.mica.classfile;

/**
 * The {@code StackMapTable} attribute of a {@code Code} attribute (JVMS §4.7.4). Each frame carries an
 * {@code offset_delta} rather than a bytecode offset: the first frame applies at {@code offset_delta}, and every
 * later one at the previous frame's offset plus {@code offset_delta + 1}. The specification chose the delta so that
 * frames are sorted by construction, and the {@code + 1} for every frame but the first so that no two frames can
 * share an offset.
 */
public final class StackMapTable {

    private StackMapTable() {}

    /**
     * The bytecode offset at which frame {@code k} applies, given the {@code offset_delta} of every frame in table
     * order.
     */
    public static int offsetOf(int[] offsetDelta, int k) {
        int offset = 0;
        for (int i = 0; i <= k; i++) {
            offset += i == 0 ? offsetDelta[i] : offsetDelta[i] + 1;
        }
        return offset;
    }
}
