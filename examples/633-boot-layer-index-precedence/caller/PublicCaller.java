import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.jar.*;
import java.util.stream.Stream;
import org.springframework.boot.jarmode.tools.ToolsJarMode;
import org.springframework.boot.loader.launch.JarLauncher;
import org.springframework.boot.loader.tools.*;

public class PublicCaller {
    static final Layer APP = new Layer("app"), DEP = new Layer("dep"), SUPPORT = new Layer("support");
    static final Layers LAYERS = new Layers() {
        public Iterator<Layer> iterator() { return stream().iterator(); }
        public Stream<Layer> stream() { return Stream.of(DEP,SUPPORT,APP); }
        public Layer getLayer(String name) { return name.startsWith("org/springframework/boot/loader/") ? SUPPORT : APP; }
        public Layer getLayer(Library lib) { return lib.getName().equals("fixture-dependency.jar") ? DEP : SUPPORT; }
    };
    static final String MARKER = "BOOT-INF/classes/sample/marker.txt";
    static String owner(Path out, String entry, byte[] expected) throws Exception {
        var owners = new ArrayList<String>();
        try (var folders = Files.list(out)) {
            for (var layer : folders.filter(Files::isDirectory).toList()) {
                var file = layer.resolve(entry);
                if (Files.isRegularFile(file)) {
                    if (!Arrays.equals(expected,Files.readAllBytes(file))) throw new AssertionError("changed extracted bytes");
                    owners.add(layer.getFileName().toString());
                }
            }
        }
        return owners.size() == 1 ? owners.getFirst() : owners.toString();
    }
    static String run(boolean sibling, boolean mixed) throws Exception {
        Path dir = Files.createTempDirectory("layers");
        Path dep = PackagingFixture.jar(dir.resolve("fixture-dependency.jar"),Map.of("value.txt",PackagingFixture.text("library")));
        Path tools = PackagingFixture.origin(ToolsJarMode.class);
        var resources = new LinkedHashMap<String,byte[]>();
        resources.put("sample/marker.txt",PackagingFixture.text("marker"));
        if (sibling) resources.put("sample/deep/sibling.txt",PackagingFixture.text("sibling"));
        Path generated = PackagingFixture.packageApp(dir,false,resources,PackagingFixture.toolSupport(List.of(new Library(dep.toFile(),LibraryScope.COMPILE),
                new Library(tools.toFile(),LibraryScope.COMPILE))),LAYERS);
        Path app = dir.resolve("app.jar");
        try (var base = new JarFile(generated.toFile()); var launcher = new JarFile(PackagingFixture.origin(JarLauncher.class).toFile());
             var out = new JarOutputStream(Files.newOutputStream(app))) {
            String indexPath = base.getManifest().getMainAttributes().getValue("Spring-Boot-Layers-Index");
            String idx = new String(PackagingFixture.read(base,indexPath),StandardCharsets.UTF_8);
            if (!idx.contains("\"BOOT-INF/lib/fixture-dependency.jar\"") || !idx.contains("\"BOOT-INF/classes/\""))
                throw new AssertionError("fixture lacks exact and directory rules: " + idx);
            if (!Arrays.equals(PackagingFixture.read(base,"BOOT-INF/lib/" + tools.getFileName()),Files.readAllBytes(tools)))
                throw new AssertionError("nested extractor bytes differ");
            for (var e : Collections.list(base.entries())) {
                if (e.getName().startsWith("org/springframework/boot/loader/")) continue;
                byte[] bytes = PackagingFixture.read(base,e.getName());
                if (mixed && e.getName().equals(indexPath)) bytes = PackagingFixture.text(
                        "- \"first\":\n  - \"BOOT-INF/classes/sample/\"\n- \"second\":\n  - \"" + MARKER + "\"\n" + idx);
                PackagingFixture.entry(out,e.getName(),bytes,e.getMethod()==JarEntry.STORED);
            }
            for (var e : Collections.list(launcher.entries())) {
                if (e.getName().startsWith("org/springframework/boot/loader/"))
                    PackagingFixture.entry(out,e.getName(),PackagingFixture.read(launcher,e.getName()),false);
            }
        }
        Path out = dir.resolve("extracted");
        var cli = PackagingFixture.java(dir,"-Djarmode=tools","-jar",app.toString(),"extract","--layers","--launcher","--destination",out.toString());
        if (cli.status() != 0) throw new IllegalStateException("layer extraction failed: " + cli.console().lines().limit(4).toList());
        String marker = owner(out,MARKER,PackagingFixture.text("marker"));
        if (mixed) return marker;
        String library = owner(out,"BOOT-INF/lib/fixture-dependency.jar",Files.readAllBytes(dep));
        return marker + ":marker/" + library + ":library" + (sibling ? "/" + owner(out,"BOOT-INF/classes/sample/deep/sibling.txt",PackagingFixture.text("sibling")) + ":sibling" : "");
    }
    public static String observe(String[] args) throws Exception {
        return switch(args[0]) {
            case "intent" -> run(false,false);
            case "control" -> run(false,false) + ";" + run(true,false);
            case "challenge" -> run(false,true);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
