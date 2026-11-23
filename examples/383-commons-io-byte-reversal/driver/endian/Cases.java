import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "reverseInt", "arguments", new String[]{"0"}),
                fields("holds", ByteReversal.reverseInt(0)), fields());
        row(1, fields("entry", "reverseInt", "arguments", new String[]{"1"}),
                fields("holds", ByteReversal.reverseInt(1)), fields());
        row(2, fields("entry", "reverseInt", "arguments", new String[]{"-1"}),
                fields("holds", ByteReversal.reverseInt(-1)), fields());
        row(3, fields("entry", "reverseInt", "arguments", new String[]{"Integer.MIN_VALUE"}),
                fields("holds", ByteReversal.reverseInt(Integer.MIN_VALUE)), fields());
        row(4, fields("entry", "reverseInt", "arguments", new String[]{"Integer.MAX_VALUE"}),
                fields("holds", ByteReversal.reverseInt(Integer.MAX_VALUE)), fields());
        row(5, fields("entry", "reverseLong", "arguments", new String[]{"0L"}),
                fields("holds", ByteReversal.reverseLong(0L)), fields());
        row(6, fields("entry", "reverseLong", "arguments", new String[]{"1L"}),
                fields("holds", ByteReversal.reverseLong(1L)), fields());
        row(7, fields("entry", "reverseLong", "arguments", new String[]{"-1L"}),
                fields("holds", ByteReversal.reverseLong(-1L)), fields());
        row(8, fields("entry", "reverseLong", "arguments", new String[]{"Long.MIN_VALUE"}),
                fields("holds", ByteReversal.reverseLong(Long.MIN_VALUE)), fields());
        row(9, fields("entry", "reverseLong", "arguments", new String[]{"Long.MAX_VALUE"}),
                fields("holds", ByteReversal.reverseLong(Long.MAX_VALUE)), fields());
        row(10, fields("entry", "rotateInt", "arguments", new String[]{"0"}),
                fields("holds", ByteReversal.rotateInt(0)), fields());
        row(11, fields("entry", "rotateInt", "arguments", new String[]{"-1"}),
                fields("holds", ByteReversal.rotateInt(-1)), fields());
        row(12, fields("entry", "rotateInt", "arguments", new String[]{"1"}),
                fields("holds", ByteReversal.rotateInt(1)), fields());
        row(13, fields("entry", "rotateLong", "arguments", new String[]{"0L"}),
                fields("holds", ByteReversal.rotateLong(0L)), fields());
        row(14, fields("entry", "rotateLong", "arguments", new String[]{"-1L"}),
                fields("holds", ByteReversal.rotateLong(-1L)), fields());
        row(15, fields("entry", "rotateLong", "arguments", new String[]{"1L"}),
                fields("holds", ByteReversal.rotateLong(1L)), fields());
    }
}
