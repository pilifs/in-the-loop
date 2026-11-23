import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "dispatch", "arguments", new String[]{"0", "0"}),
                fields("holds", DefaultDispatch.dispatch(0, 0)), fields());
        row(1, fields("entry", "dispatch", "arguments", new String[]{"0", "1"}),
                fields("holds", DefaultDispatch.dispatch(0, 1)), fields());
        row(2, fields("entry", "dispatch", "arguments", new String[]{"0", "-1"}),
                fields("holds", DefaultDispatch.dispatch(0, -1)), fields());
        row(3, fields("entry", "dispatch", "arguments", new String[]{"0", "Integer.MIN_VALUE"}),
                fields("holds", DefaultDispatch.dispatch(0, Integer.MIN_VALUE)), fields());
        row(4, fields("entry", "dispatch", "arguments", new String[]{"0", "Integer.MAX_VALUE"}),
                fields("holds", DefaultDispatch.dispatch(0, Integer.MAX_VALUE)), fields());
        row(5, fields("entry", "dispatch", "arguments", new String[]{"1", "0"}),
                fields("holds", DefaultDispatch.dispatch(1, 0)), fields());
        row(6, fields("entry", "dispatch", "arguments", new String[]{"1", "1"}),
                fields("holds", DefaultDispatch.dispatch(1, 1)), fields());
        row(7, fields("entry", "dispatch", "arguments", new String[]{"1", "-1"}),
                fields("holds", DefaultDispatch.dispatch(1, -1)), fields());
        row(8, fields("entry", "dispatch", "arguments", new String[]{"1", "Integer.MIN_VALUE"}),
                fields("holds", DefaultDispatch.dispatch(1, Integer.MIN_VALUE)), fields());
        row(9, fields("entry", "dispatch", "arguments", new String[]{"1", "Integer.MAX_VALUE"}),
                fields("holds", DefaultDispatch.dispatch(1, Integer.MAX_VALUE)), fields());
        row(10, fields("entry", "dispatch", "arguments", new String[]{"2", "0"}),
                fields("holds", DefaultDispatch.dispatch(2, 0)), fields());
        row(11, fields("entry", "dispatch", "arguments", new String[]{"2", "1"}),
                fields("holds", DefaultDispatch.dispatch(2, 1)), fields());
        row(12, fields("entry", "dispatch", "arguments", new String[]{"2", "-1"}),
                fields("holds", DefaultDispatch.dispatch(2, -1)), fields());
        row(13, fields("entry", "dispatch", "arguments", new String[]{"2", "Integer.MIN_VALUE"}),
                fields("holds", DefaultDispatch.dispatch(2, Integer.MIN_VALUE)), fields());
        row(14, fields("entry", "dispatch", "arguments", new String[]{"2", "Integer.MAX_VALUE"}),
                fields("holds", DefaultDispatch.dispatch(2, Integer.MAX_VALUE)), fields());
        row(15, fields("entry", "firstDeclared", "arguments", new String[]{"0"}),
                fields("holds", DefaultDispatch.firstDeclared(0)), fields());
        row(16, fields("entry", "firstDeclared", "arguments", new String[]{"1"}),
                fields("holds", DefaultDispatch.firstDeclared(1)), fields());
        row(17, fields("entry", "firstDeclared", "arguments", new String[]{"-1"}),
                fields("holds", DefaultDispatch.firstDeclared(-1)), fields());
        row(18, fields("entry", "firstDeclared", "arguments", new String[]{"Integer.MIN_VALUE"}),
                fields("holds", DefaultDispatch.firstDeclared(Integer.MIN_VALUE)), fields());
        row(19, fields("entry", "firstDeclared", "arguments", new String[]{"Integer.MAX_VALUE"}),
                fields("holds", DefaultDispatch.firstDeclared(Integer.MAX_VALUE)), fields());
    }
}
