package paper;

import java.nio.file.Path;
import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class PaperCases {
    public static void main(String[] args) throws Exception {
        if (args.length == 2 && args[0].equals("child")) {
            int id = Integer.parseInt(args[1]);
            Scenario.set(id / 3);
            String first = Paper.size();
            Scenario.set(id % 3);
            String second = Paper.size();
            
            Grid.row(id, new int[]{id / 3, id % 3}, fields("first", first, "second", second, "count", Paper.initializations),
                    fields("second", Scenario.value(id), "count", Scenario.count(id)));
            return;
        }
        for (int i = 0; i < 9; i++) {
            Process p = new ProcessBuilder(Path.of(System.getProperty("java.home"), "bin", "java").toString(),
                    "-cp", System.getProperty("java.class.path"), "paper.PaperCases", "child", Integer.toString(i))
                    .inheritIO().start();
            if (p.waitFor() != 0) throw new AssertionError("fresh paper JVM failed");
        }
    }
}
