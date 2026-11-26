import picocli.CommandLine;
import picocli.CommandLine.*;

import java.util.*;

public class PublicCaller {
    @Command(name = "root")
    static class NullParent {
        @Option(names = "-D", scope = ScopeType.INHERIT, mapFallbackValue = Option.NULL_VALUE)
        Map<String, String> map = new LinkedHashMap<>();
    }

    @Command(name = "root")
    static class EmptyParent {
        @Option(names = "-D", scope = ScopeType.INHERIT, mapFallbackValue = "")
        Map<String, String> map = new LinkedHashMap<>();
    }

    @Command(name = "sub")
    static class Child {}

    static String parse(boolean empty, boolean child, boolean explicit) {
        var n = new NullParent();
        var e = new EmptyParent();
        var cmd = new CommandLine(empty ? e : n).addSubcommand("sub", new Child());
        String operand = explicit ? "-Dkey=actual" : "-Dkey";
        cmd.parseArgs(child ? new String[] {"sub", operand} : new String[] {operand});
        var map = empty ? e.map : n.map;
        String v = map.get("key");
        return map.size()
                + "/"
                + map.containsKey("key")
                + "/"
                + (v == null ? "<null>" : v.isEmpty() ? "empty" : v);
    }

    public static String observe(String[] a) {
        if (a[0].equals("challenge"))
            return parse(true, false, false)
                    + " / "
                    + parse(true, true, false)
                    + " / "
                    + parse(false, false, false)
                    + " / "
                    + parse(false, true, false);
        return parse(false, true, a[0].equals("control"));
    }
}
