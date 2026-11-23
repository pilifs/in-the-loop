import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "fraction", "arguments", new String[]{"16777216"}),
                fields("holds", WideNumbers.fraction(16777216)), fields());
        row(1, fields("entry", "fraction", "arguments", new String[]{"16777217"}),
                fields("holds", WideNumbers.fraction(16777217)), fields());
        row(2, fields("entry", "fraction", "arguments", new String[]{"16777219"}),
                fields("holds", WideNumbers.fraction(16777219)), fields());
        row(3, fields("entry", "fraction", "arguments", new String[]{"33554431"}),
                fields("holds", WideNumbers.fraction(33554431)), fields());
        row(4, fields("entry", "fractionOpcode", "arguments", new String[]{"16777216"}),
                fields("holds", WideNumbers.fractionOpcode(16777216)), fields());
        row(5, fields("entry", "fractionOpcode", "arguments", new String[]{"16777217"}),
                fields("holds", WideNumbers.fractionOpcode(16777217)), fields());
        row(6, fields("entry", "fractionOpcode", "arguments", new String[]{"16777219"}),
                fields("holds", WideNumbers.fractionOpcode(16777219)), fields());
        row(7, fields("entry", "fractionOpcode", "arguments", new String[]{"33554431"}),
                fields("holds", WideNumbers.fractionOpcode(33554431)), fields());
        row(8, fields("entry", "floorOnly", "arguments", new String[]{"16777216"}),
                fields("holds", WideNumbers.floorOnly(16777216)), fields());
        row(9, fields("entry", "floorOnly", "arguments", new String[]{"16777219"}),
                fields("holds", WideNumbers.floorOnly(16777219)), fields());
        row(10, fields("entry", "floorOnly", "arguments", new String[]{"33554431"}),
                fields("holds", WideNumbers.floorOnly(33554431)), fields());
        row(11, fields("entry", "narrow", "arguments", new String[]{"0L"}),
                fields("holds", WideNumbers.narrow(0L)), fields());
        row(12, fields("entry", "narrow", "arguments", new String[]{"1L"}),
                fields("holds", WideNumbers.narrow(1L)), fields());
        row(13, fields("entry", "narrow", "arguments", new String[]{"0xfffffffffffffL"}),
                fields("holds", WideNumbers.narrow(0xfffffffffffffL)), fields());
        row(14, fields("entry", "narrow", "arguments", new String[]{"-1L"}),
                fields("holds", WideNumbers.narrow(-1L)), fields());
        row(15, fields("entry", "narrowOpcode", "arguments", new String[]{"0L"}),
                fields("holds", WideNumbers.narrowOpcode(0L)), fields());
        row(16, fields("entry", "narrowOpcode", "arguments", new String[]{"1L"}),
                fields("holds", WideNumbers.narrowOpcode(1L)), fields());
        row(17, fields("entry", "narrowOpcode", "arguments", new String[]{"0xfffffffffffffL"}),
                fields("holds", WideNumbers.narrowOpcode(0xfffffffffffffL)), fields());
        row(18, fields("entry", "narrowOpcode", "arguments", new String[]{"-1L"}),
                fields("holds", WideNumbers.narrowOpcode(-1L)), fields());
        row(19, fields("entry", "wraps", "arguments", new String[]{"0L"}),
                fields("holds", WideNumbers.wraps(0L)), fields());
        row(20, fields("entry", "wraps", "arguments", new String[]{"1L"}),
                fields("holds", WideNumbers.wraps(1L)), fields());
        row(21, fields("entry", "wraps", "arguments", new String[]{"0xfffffffffffffL"}),
                fields("holds", WideNumbers.wraps(0xfffffffffffffL)), fields());
        row(22, fields("entry", "wraps", "arguments", new String[]{"-1L"}),
                fields("holds", WideNumbers.wraps(-1L)), fields());
    }
}
