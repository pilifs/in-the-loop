import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;
import org.apache.calcite.runtime.Hook;

public class GeneratedAccumulator {
    public static void main(String[] args) throws Exception {
        List<String> programs = new ArrayList<>();
        try (Hook.Closeable capture = Hook.JAVA_PLAN.addThread((Consumer<String>)programs::add)) {
            String value = UpgradeProbe.observe(args);
            if (programs.size() != 1) throw new AssertionError("expected one generated, executed query plan: " + programs.size());
            Files.write(Paths.get("observation.txt"),value.getBytes(StandardCharsets.UTF_8));
            Files.write(Paths.get("program.java"),programs.get(0).getBytes(StandardCharsets.UTF_8));
        }
    }
}
