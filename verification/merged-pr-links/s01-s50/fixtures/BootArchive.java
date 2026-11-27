import java.io.*;
import java.net.URI;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.jar.*;
import java.util.zip.CRC32;
import java.util.zip.ZipEntry;
import org.springframework.boot.loader.launch.JarLauncher;
import org.springframework.boot.loader.net.protocol.jar.JarUrlClassLoader;

/** Runs a fixture's Start-Class through the original Boot launcher and nested libraries. */
public final class BootArchive {
    private BootArchive() {}
    static final String BINDING = "org/springframework/boot/loader/net/protocol/jar/JarUrlClassLoader.class";

    static byte[] bytes(Class<?> type) throws IOException {
        String path = "/" + type.getName().replace('.', '/') + ".class";
        try (InputStream in = type.getResourceAsStream(path)) { return Objects.requireNonNull(in, path).readAllBytes(); }
    }

    static void entry(JarOutputStream out, String name, byte[] bytes, boolean stored) throws IOException {
        JarEntry item = new JarEntry(name);
        item.setTime(315532800000L);
        if (stored) {
            CRC32 crc = new CRC32();
            crc.update(bytes);
            item.setMethod(ZipEntry.STORED);
            item.setSize(bytes.length);
            item.setCrc(crc.getValue());
        }
        out.putNextEntry(item);
        out.write(bytes);
        out.closeEntry();
    }

    static Manifest manifest() {
        Manifest m = new Manifest();
        m.getMainAttributes().putValue("Manifest-Version", "1.0");
        return m;
    }

    static byte[] library(Manifest manifest, Map<String, byte[]> files) throws IOException {
        var buf = new ByteArrayOutputStream();
        try (var out = new JarOutputStream(buf, manifest)) {
            for (var e : files.entrySet()) entry(out, e.getKey(), e.getValue(), false);
        }
        return buf.toByteArray();
    }

    static byte[] codeSource(Class<?> type) throws Exception {
        return Files.readAllBytes(Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()));
    }

    static void childBinding() throws Exception {
        ClassLoader loader = Thread.currentThread().getContextClassLoader();
        if (!loader.getClass().getName().equals("org.springframework.boot.loader.launch.LaunchedClassLoader")) {
            throw new AssertionError("fixture is outside the launched application");
        }
        String digest = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes(JarUrlClassLoader.class)));
        if (!digest.equals(System.getProperty("fixture.loader.digest"))) throw new AssertionError("different loader bytes");
    }

    static String launch(Class<?> application, Map<String, byte[]> resources, Map<String, byte[]> libraries,
                         String mode) throws Exception {
        Path dir = Files.createTempDirectory("spring-executable");
        Path executable = dir.resolve("fixture.jar");
        var original = Path.of(JarLauncher.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        var m = manifest();
        m.getMainAttributes().putValue("Main-Class", JarLauncher.class.getName());
        m.getMainAttributes().putValue("Start-Class", application.getName());
        try (var input = new JarFile(original.toFile());
             var out = new JarOutputStream(Files.newOutputStream(executable), m)) {
            for (JarEntry jarEntry : Collections.list(input.entries())) {
                if (jarEntry.isDirectory() || !jarEntry.getName().startsWith("org/springframework/boot/loader/")) continue;
                try (var stream = input.getInputStream(jarEntry)) { entry(out, jarEntry.getName(), stream.readAllBytes(), false); }
            }
            for (String name : List.of("BOOT-INF/", "BOOT-INF/classes/", "BOOT-INF/lib/")) entry(out, name, new byte[0], false);
            for (Class<?> type : List.of(application, BootArchive.class))
                entry(out, "BOOT-INF/classes/" + type.getName().replace('.', '/') + ".class", bytes(type), false);
            for (var e : resources.entrySet()) entry(out, "BOOT-INF/classes/" + e.getKey(), e.getValue(), false);
            for (var e : libraries.entrySet()) entry(out, "BOOT-INF/lib/" + e.getKey(), e.getValue(), true);
        }
        String expected = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes(JarUrlClassLoader.class)));
        Path log = dir.resolve("child.log");
        Process child = new ProcessBuilder(Path.of(System.getProperty("java.home"), "bin", "java").toString(),
                "-Xmx128m", "-Dfixture.loader.digest=" + expected, "-jar", executable.toString(), mode)
                .directory(dir.toFile()).redirectErrorStream(true).redirectOutput(log.toFile()).start();
        try {
            if (!child.waitFor(15, TimeUnit.SECONDS)) throw new AssertionError("executable did not terminate");
            var lines = Files.readAllLines(log);
            if (child.exitValue() != 0) throw new IOException("executable failed: " + String.join(" ", lines).substring(0,
                    Math.min(400, String.join(" ", lines).length())));
            var answers = lines.stream().filter(s -> s.startsWith("OBS ")).toList();
            if (answers.size() != 1) throw new IOException("expected one original program result");
            return answers.getFirst().substring(4);
        } finally { if (child.isAlive()) child.destroyForcibly(); }
    }
}
