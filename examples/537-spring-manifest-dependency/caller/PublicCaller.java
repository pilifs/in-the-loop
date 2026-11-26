import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.jar.*;

public class PublicCaller {
    static void jar(Path file, Manifest manifest, String name, byte[] bytes) throws Exception {
        Files.createDirectories(file.getParent());
        try (var out = new JarOutputStream(Files.newOutputStream(file), manifest)) {
            out.putNextEntry(new JarEntry(name));
            out.write(bytes);
            out.closeEntry();
        }
    }

    static Manifest manifest() {
        var m = new Manifest();
        m.getMainAttributes().put(Attributes.Name.MANIFEST_VERSION, "1.0");
        return m;
    }

    static String launch(Path root, boolean relative, String value) throws Exception {
        Path asset = root.resolve("lib/asset.jar"), launch = root.resolve("launcher.jar");
        jar(asset, manifest(), "assets/q30.txt", value.getBytes(StandardCharsets.UTF_8));
        jar(
                root.resolve("decoy/asset.jar"),
                manifest(),
                "assets/q30.txt",
                "amber".getBytes(StandardCharsets.UTF_8));
        List<String> entries = new ArrayList<>();
        entries.add(relative ? "lib/asset.jar" : asset.toString());
        for (String item : System.getProperty("java.class.path").split(File.pathSeparator)) {
            Path dependency = Path.of(item);
            if (Files.isRegularFile(dependency)) entries.add(dependency.toUri().toASCIIString());
        }
        var m = manifest();
        m.getMainAttributes().put(Attributes.Name.MAIN_CLASS, "AssetReader");
        m.getMainAttributes().put(Attributes.Name.CLASS_PATH, String.join(" ", entries));
        try (var in = PublicCaller.class.getResourceAsStream("/AssetReader.class")) {
            jar(launch, m, "AssetReader.class", in.readAllBytes());
        }
        String origin =
                PathMatchingResourcePatternResolver.class
                        .getProtectionDomain()
                        .getCodeSource()
                        .getLocation()
                        .toURI()
                        .getPath();
        Process child =
                new ProcessBuilder(
                                Path.of(System.getProperty("java.home"), "bin", "java").toString(),
                                "-XX:-UsePerfData",
                                "-Xmx96m",
                                "-jar",
                                launch.toString(),
                                origin)
                        .directory(root.toFile())
                        .redirectErrorStream(true)
                        .start();
        if (!child.waitFor(10, TimeUnit.SECONDS)) {
            child.destroyForcibly();
            throw new IOException("JAR launch timed out");
        }
        String output = new String(child.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        if (child.exitValue() != 0) throw new IOException(output);
        return output.lines()
                .filter(line -> line.startsWith("assets="))
                .findFirst()
                .orElseThrow()
                .substring(7);
    }

    public static String observe(String[] args) throws Exception {
        Path root = Path.of("deployment").toAbsolutePath();
        String first = launch(root, args[0].equals("relative"), "amber");
        return args[0].equals("replace") ? first + "/" + launch(root, false, "cobalt") : first;
    }
}
