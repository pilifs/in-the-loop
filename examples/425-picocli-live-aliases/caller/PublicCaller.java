import java.io.PrintWriter;
import java.io.StringWriter;
import java.util.concurrent.Callable;
import picocli.CommandLine;
import picocli.CommandLine.Command;

public class PublicCaller {
    @Command(name = "main", subcommands = Child.class)
    static class Main implements Runnable { public void run() {} }

    @Command(name = "sub")
    static class Child implements Callable<Integer> {
        int calls;
        public Integer call() { calls++; return 0; }
    }

    static CommandLine root() {
        var root = new CommandLine(new Main());
        root.setErr(new PrintWriter(new StringWriter()));
        return root;
    }

    static String execute(CommandLine root, Child child, String token) {
        int code = root.execute(token);
        return code + "/" + child.calls;
    }

    public static String observe(String[] args) {
        var root = root();
        var spec = root.getSubcommands().get("sub").getCommandSpec();
        var child = (Child) spec.userObject();
        if (args[0].equals("control")) {
            String before = execute(root, child, "sub") + "," + execute(root, child, "unknown");
            spec.aliases("distinct");
            return before + "," + execute(root, child, "sub") + "," + execute(root, child, "unknown");
        }
        if (args[0].equals("primary")) {
            spec.aliases("sub");
            spec.aliases(new String[0]);
            var fresh = root();
            Child other = fresh.getSubcommands().get("sub").getCommand();
            return "edited=" + root.getSubcommands().containsKey("sub") + "/" + execute(root, child, "sub")
                    + " fresh=" + fresh.getSubcommands().containsKey("sub") + "/" + execute(fresh, other, "sub");
        }
        spec.aliases("first");
        String first = execute(root, child, "first");
        spec.aliases("second");
        return first + "," + execute(root, child, "first") + "," + execute(root, child, "second");
    }
}
