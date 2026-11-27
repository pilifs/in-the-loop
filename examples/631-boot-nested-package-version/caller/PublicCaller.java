import java.io.*;
import java.util.*;
import java.util.jar.*;

public class PublicCaller {
    static String run(boolean directory, boolean missingFirst) throws Exception {
        var m = BootArchive.manifest();
        m.getMainAttributes().putValue("Implementation-Version", "1.2.3");
        var entries = new LinkedHashMap<String,byte[]>();
        if (directory) entries.put("demo/", new byte[0]);
        entries.put("demo/Application.class", BootArchive.bytes(demo.Application.class));
        byte[] library = BootArchive.library(m, entries);
        try (var zip = new JarInputStream(new ByteArrayInputStream(library))) {
            if (!"1.2.3".equals(zip.getManifest().getMainAttributes().getValue("Implementation-Version")))
                throw new AssertionError("manifest not in original library");
        }
        return BootArchive.launch(NestedApp.class, Map.of(), Map.of("sample.jar", library), missingFirst ? "miss" : "first");
    }
    public static String observe(String[] args) throws Exception {
        return switch (args[0]) {
            case "intent" -> run(false,false);
            case "control" -> run(true,false);
            case "challenge" -> run(false,false) + "/" + run(false,true);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
