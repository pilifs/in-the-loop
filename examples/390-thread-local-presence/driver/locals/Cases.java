import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "kernel", "arguments", new String[]{"0"}),
                fields("holds", ThreadLocalHistory.kernel(0)), fields());
        row(1, fields("entry", "kernel", "arguments", new String[]{"1"}),
                fields("holds", ThreadLocalHistory.kernel(1)), fields());
        row(2, fields("entry", "kernel", "arguments", new String[]{"2"}),
                fields("holds", ThreadLocalHistory.kernel(2)), fields());
        row(3, fields("entry", "kernel", "arguments", new String[]{"3"}),
                fields("holds", ThreadLocalHistory.kernel(3)), fields());
        row(4, fields("entry", "spring", "arguments", new String[]{"0"}),
                fields("holds", ThreadLocalHistory.spring(0)), fields());
        row(5, fields("entry", "spring", "arguments", new String[]{"1"}),
                fields("holds", ThreadLocalHistory.spring(1)), fields());
        row(6, fields("entry", "spring", "arguments", new String[]{"2"}),
                fields("holds", ThreadLocalHistory.spring(2)), fields());
        row(7, fields("entry", "spring", "arguments", new String[]{"3"}),
                fields("holds", ThreadLocalHistory.spring(3)), fields());
        row(8, fields("entry", "nullInitializes", "arguments", new String[]{"false"}),
                fields("holds", ThreadLocalHistory.nullInitializes(false)), fields());
        row(9, fields("entry", "nullInitializes", "arguments", new String[]{"true"}),
                fields("holds", ThreadLocalHistory.nullInitializes(true)), fields());
    }
}
