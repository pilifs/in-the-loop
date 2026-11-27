import java.io.FileNotFoundException;
import java.util.*;

public class NestedApp {
    public static void main(String[] args) throws Exception {
        BootArchive.childBinding();
        var names = args[0].equals("control") ? List.of("dir/a-b.txt")
                : args[0].equals("challenge") ? List.of("dir with space/a#b.txt", "dir with space/a%23b.txt")
                : List.of("dir with space/a#b.txt");
        var observed = new ArrayList<String>();
        ClassLoader loader = Thread.currentThread().getContextClassLoader();
        for (var name : names) {
            var url = loader.getResource(name);
            if (url == null) { observed.add("missing"); continue; }
            try (var input = url.openStream()) {
                int first = input.read();
                observed.add(input.read() == -1 ? Integer.toString(first) : "extra");
            } catch (FileNotFoundException missing) { observed.add("FileNotFoundException"); }
        }
        System.out.println("OBS " + String.join(",",observed));
    }
}
