import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "hex", "arguments", new String[]{"16"}),
                fields("holds", RadixDigits.hex(16)), fields());
        row(1, fields("entry", "hex", "arguments", new String[]{"190"}),
                fields("holds", RadixDigits.hex(190)), fields());
        row(2, fields("entry", "hex", "arguments", new String[]{"255"}),
                fields("holds", RadixDigits.hex(255)), fields());
        row(3, fields("entry", "lowFirst", "arguments", new String[]{"17"}),
                fields("holds", RadixDigits.lowFirst(17)), fields());
        row(4, fields("entry", "lowFirst", "arguments", new String[]{"190"}),
                fields("holds", RadixDigits.lowFirst(190)), fields());
    }
}
