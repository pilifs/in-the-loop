import java.io.*;
import java.util.*;
import java.util.jar.*;

public class PublicCaller {
    static int independent(byte[] jar, String name) throws IOException {
        try (var input = new JarInputStream(new ByteArrayInputStream(jar))) {
            for (JarEntry e; (e = input.getNextJarEntry()) != null;) {
                if (e.getName().equals(name)) {
                    int b = input.read();
                    if (input.read() != -1) throw new IOException("expected one byte");
                    return b;
                }
            }
        }
        throw new IOException("fixture missing");
    }
    public static String observe(String[] args) throws Exception {
        var names = args[0].equals("control") ? List.of("dir/a-b.txt")
                : args[0].equals("challenge") ? List.of("dir with space/a#b.txt", "dir with space/a%23b.txt")
                : List.of("dir with space/a#b.txt");
        var entries = new LinkedHashMap<String,byte[]>();
        for (String name : names) entries.put(name, new byte[] {(byte) (name.contains("%") ? 99 : name.contains("#") ? 42 : 17)});
        byte[] library = BootArchive.library(BootArchive.manifest(), entries);
        String[] reads = BootArchive.launch(NestedApp.class, Map.of(), Map.of("sample.jar", library), args[0]).split(",");
        var results = new ArrayList<String>();
        for (int i = 0; i < names.size(); i++) results.add(reads[i] + "/" + independent(library, names.get(i)));
        return String.join(",", results);
    }
}
