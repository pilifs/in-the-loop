import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "NodeChecks#direct", "arguments", new String[]{"1L << 54"}),
                fields("holds", NodeChecks.direct(1L << 54)), fields());
        row(1, fields("entry", "NodeChecks#direct", "arguments", new String[]{"0x0040000040000001L"}),
                fields("holds", NodeChecks.direct(0x0040000040000001L)), fields());
        row(2, fields("entry", "NodeChecks#direct", "arguments", new String[]{"(1L << 55) - 1"}),
                fields("holds", NodeChecks.direct((1L << 55) - 1)), fields());
        row(3, fields("entry", "NodeChecks#same", "arguments", new String[]{"1L << 54"}),
                fields("holds", NodeChecks.same(1L << 54)), fields());
        row(4, fields("entry", "NodeChecks#same", "arguments", new String[]{"0x0040000040000001L"}),
                fields("holds", NodeChecks.same(0x0040000040000001L)), fields());
        row(5, fields("entry", "NodeChecks#publicSubnormal", "arguments", new String[]{"0x1p-150"}),
                fields("holds", NodeChecks.publicSubnormal(0x1p-150)), fields());
        row(6, fields("entry", "NodeChecks#publicSubnormal", "arguments", new String[]{"Math.nextUp(0x1p-150)"}),
                fields("holds", NodeChecks.publicSubnormal(Math.nextUp(0x1p-150))), fields());
        row(7, fields("entry", "NodeChecks#publicSubnormal", "arguments", new String[]{"0x1p-149"}),
                fields("holds", NodeChecks.publicSubnormal(0x1p-149)), fields());
        row(8, fields("entry", "NodeChecks#wrongSubnormal", "arguments", new String[]{"0x1p-149"}),
                fields("holds", NodeChecks.wrongSubnormal(0x1p-149)), fields());
        row(9, fields("entry", "NodeChecks#wrongSubnormal", "arguments", new String[]{"0x1p-150"}),
                fields("holds", NodeChecks.wrongSubnormal(0x1p-150)), fields());
        row(10, fields("entry", "NodeChecks#commons", "arguments", new String[]{"1L << 54"}),
                fields("holds", NodeChecks.commons(1L << 54)), fields());
        row(11, fields("entry", "NodeChecks#commons", "arguments", new String[]{"0x0040000040000001L"}),
                fields("holds", NodeChecks.commons(0x0040000040000001L)), fields());
        row(12, fields("entry", "NodeChecks#commons", "arguments", new String[]{"(1L << 55) - 1"}),
                fields("holds", NodeChecks.commons((1L << 55) - 1)), fields());
        row(13, fields("entry", "ConversionEquivalence#classified", "arguments", new String[]{"1L << 54"}),
                fields("holds", ConversionEquivalence.classified(1L << 54)), fields());
        row(14, fields("entry", "ConversionEquivalence#classified", "arguments", new String[]{"0x0040000040000001L"}),
                fields("holds", ConversionEquivalence.classified(0x0040000040000001L)), fields());
        row(15, fields("entry", "ConversionEquivalence#classified", "arguments", new String[]{"(1L << 55) - 1"}),
                fields("holds", ConversionEquivalence.classified((1L << 55) - 1)), fields());
        row(16, fields("entry", "NodeChecks#intrinsicSubnormal", "arguments", new String[]{"0x1p-150"}),
                fields("holds", NodeChecks.intrinsicSubnormal(0x1p-150)), fields());
        row(17, fields("entry", "NodeChecks#intrinsicSubnormal", "arguments", new String[]{"Math.nextUp(0x1p-150)"}),
                fields("holds", NodeChecks.intrinsicSubnormal(Math.nextUp(0x1p-150))), fields());
        row(18, fields("entry", "NodeChecks#intrinsicSubnormal", "arguments", new String[]{"0x1p-149"}),
                fields("holds", NodeChecks.intrinsicSubnormal(0x1p-149)), fields());
        row(19, fields("entry", "NodeChecks#mantissaSubnormal", "arguments", new String[]{"0L"}),
                fields("holds", NodeChecks.mantissaSubnormal(0L)), fields());
        row(20, fields("entry", "NodeChecks#mantissaSubnormal", "arguments", new String[]{"1L"}),
                fields("holds", NodeChecks.mantissaSubnormal(1L)), fields());
        row(21, fields("entry", "NodeChecks#mantissaSubnormal", "arguments", new String[]{"-1L"}),
                fields("holds", NodeChecks.mantissaSubnormal(-1L)), fields());
    }
}
