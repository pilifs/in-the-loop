import java.nio.file.Path;

/** Execute the registered filesystem history through a full Gradle installation's own launcher. */
public class FullHistory {
    public static void main(String[] args) throws Exception {
        System.out.println(PublicCaller.history(args[0], Path.of("").toAbsolutePath(), Path.of(args[1]), args[2]));
    }
}
