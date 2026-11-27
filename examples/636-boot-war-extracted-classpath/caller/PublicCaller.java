import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.jar.*;
import org.springframework.boot.jarmode.tools.ToolsJarMode;
import org.springframework.boot.loader.tools.*;

public class PublicCaller {
    static String extract(boolean war,boolean collision) throws Exception {
        Path dir = Files.createTempDirectory("boot-package");
        String second = collision ? "common.jar" : "provided.jar";
        String first = collision ? "common.jar" : "ordinary.jar";
        Path reg = PackagingFixture.jar(dir.resolve("a").resolve(first),Map.of("regular-marker.txt",PackagingFixture.text("REG")));
        Path prov = PackagingFixture.jar(dir.resolve("b").resolve(second),Map.of("provided-marker.txt",PackagingFixture.text("PROV")));
        Path tools = PackagingFixture.origin(ToolsJarMode.class);
        var libs = List.of(new Library(reg.toFile(),LibraryScope.COMPILE),
                new Library(prov.toFile(),war ? LibraryScope.PROVIDED : LibraryScope.COMPILE),new Library(tools.toFile(),LibraryScope.COMPILE));
        var source = new LinkedHashMap<String,byte[]>();
        if (war) {
            source.put("index.html",PackagingFixture.text("front"));
            source.put("WEB-INF/jsp/hello.jsp",PackagingFixture.text("view"));
        }
        Path archive = PackagingFixture.packageApp(dir,war,source,PackagingFixture.toolSupport(libs),Layers.IMPLICIT);
        String lib = war ? "WEB-INF/lib/" : "BOOT-INF/lib/", secondary = war ? "WEB-INF/lib-provided/" : lib;
        List<String> order;
        try (var input = new JarFile(archive.toFile())) {
            var attrs = input.getManifest().getMainAttributes();
            String index = new String(PackagingFixture.read(input,attrs.getValue("Spring-Boot-Classpath-Index")),StandardCharsets.UTF_8);
            if (!index.contains(lib + first) || !index.contains(secondary + second)) throw new AssertionError("missing indexed library");
            if (!Arrays.equals(PackagingFixture.read(input,lib + tools.getFileName()),Files.readAllBytes(tools))) throw new AssertionError("different tool bytes");
            order = index.lines().map(line -> line.substring(3,line.length()-1))
                    .filter(line -> line.equals(lib+first) || line.equals(secondary+second)).map(line -> line.substring(line.lastIndexOf('/')+1)).toList();
        }
        Path extraction = Files.createDirectory(dir.resolve("extraction"));
        var run = PackagingFixture.java(extraction,"-Djarmode=tools","-jar",archive.toString(),"extract");
        if (run.status() != 0) {
            if (collision && run.console().contains("common.jar") && run.console().contains(lib+first) && run.console().contains(secondary+second))
                return "collision:both-paths";
            if (run.console().contains("Invalid library location")) return "invalid-library-location";
            throw new IllegalStateException("extract failed: " + run.console().lines().limit(4).toList());
        }
        if (collision) return "collision:accepted";
        Path output = extraction.resolve("test"), main = output.resolve("test.jar");
        boolean original = Arrays.equals(Files.readAllBytes(reg),Files.readAllBytes(output.resolve("lib").resolve(first)))
                && Arrays.equals(Files.readAllBytes(prov),Files.readAllBytes(output.resolve("lib").resolve(second)));
        try (var file = new JarFile(main.toFile())) {
            var paths = Arrays.asList(file.getManifest().getMainAttributes().getValue("Class-Path").split(" "));
            int a = paths.indexOf("lib/"+first), b = paths.indexOf("lib/"+second);
            boolean ordered = a >= 0 && b >= 0 && ((a < b) == order.getFirst().equals(first));
            String resources = "";
            if (war) resources = Arrays.equals(PackagingFixture.read(file,"META-INF/resources/index.html"),PackagingFixture.text("front"))
                    && Arrays.equals(PackagingFixture.read(file,"META-INF/resources/WEB-INF/jsp/hello.jsp"),PackagingFixture.text("view")) ? "html+jsp:" : "changed:";
            var launch = PackagingFixture.java(dir.resolve("elsewhere"),"-jar",main.toString());
            var markers = launch.console().lines().filter(s -> s.startsWith("MARKERS ")).toList();
            if (launch.status() != 0 || markers.size() != 1) throw new AssertionError("extracted program failed");
            return (original ? "both:" : "bytes-changed:") + (ordered ? "ordered:" : "unordered:") + resources + markers.getFirst().substring(8);
        }
    }
    public static String observe(String[] args) throws Exception {
        return switch (args[0]) {
            case "intent" -> extract(true,false);
            case "control" -> extract(false,false);
            case "challenge" -> extract(true,false) + "/" + extract(true,true);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
