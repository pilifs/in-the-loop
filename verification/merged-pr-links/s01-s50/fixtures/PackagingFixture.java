import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.jar.*;
import java.util.zip.*;
import org.springframework.boot.loader.tools.*;

/** Small, root-owned application archive made through Boot's public Repackager. */
public final class PackagingFixture {
    private PackagingFixture() {}

    static byte[] text(String s) { return s.getBytes(StandardCharsets.UTF_8); }
    static void entry(JarOutputStream out, String name, byte[] bytes, boolean stored) throws IOException {
        var e = new JarEntry(name);
        e.setTime(315532800000L);
        if (stored) {
            var crc = new CRC32(); crc.update(bytes);
            e.setMethod(ZipEntry.STORED); e.setSize(bytes.length); e.setCrc(crc.getValue());
        }
        out.putNextEntry(e); out.write(bytes); out.closeEntry();
    }
    static Path jar(Path file, Map<String, byte[]> contents) throws IOException {
        Files.createDirectories(file.getParent());
        var manifest = new Manifest();
        manifest.getMainAttributes().putValue("Manifest-Version","1.0");
        try (var out = new JarOutputStream(Files.newOutputStream(file),manifest)) {
            for (var e : contents.entrySet()) entry(out,e.getKey(),e.getValue(),false);
        }
        return file;
    }
    static byte[] bytes(Class<?> cls) throws IOException {
        try (var in = cls.getResourceAsStream("/" + cls.getName().replace('.','/') + ".class")) {
            return Objects.requireNonNull(in).readAllBytes();
        }
    }
    static Path origin(Class<?> cls) throws Exception {
        return Path.of(cls.getProtectionDomain().getCodeSource().getLocation().toURI());
    }
    static List<Library> toolSupport(List<Library> libraries) throws Exception {
        var all = new ArrayList<>(libraries);
        all.add(new Library(origin(org.springframework.util.ClassUtils.class).toFile(), LibraryScope.COMPILE));
        all.add(new Library(origin(org.apache.commons.logging.LogFactory.class).toFile(), LibraryScope.COMPILE));
        return all;
    }
    static byte[] read(JarFile jar,String name) throws IOException {
        var entry = jar.getJarEntry(name);
        if (entry == null) throw new IOException("missing fixture entry " + name);
        try (var in = jar.getInputStream(entry)) { return in.readAllBytes(); }
    }
    static Path packageApp(Path dir,boolean war,Map<String,byte[]> entries,List<Library> libraries,Layers layers) throws Exception {
        var contents = new LinkedHashMap<>(entries);
        contents.put((war ? "WEB-INF/classes/" : "") + "LaunchMarkers.class",bytes(LaunchMarkers.class));
        String extension = war ? ".war" : ".jar";
        Path original = jar(dir.resolve("source" + extension),contents);
        var packager = new Repackager(original.toFile());
        packager.setLayout(war ? new Layouts.War() : new Layouts.Jar());
        packager.setMainClass("LaunchMarkers");
        packager.setIncludeRelevantJarModeJars(false);
        if (layers != null) packager.setLayers(layers);
        Path out = dir.resolve("test" + extension);
        packager.repackage(out.toFile(),callback -> { for (var lib : libraries) callback.library(lib); });
        return out;
    }
    record Run(int status,String console) {}
    static Run java(Path cwd, String... args) throws Exception {
        Files.createDirectories(cwd);
        var cmd = new ArrayList<>(List.of(Path.of(System.getProperty("java.home"),"bin","java").toString(),"-Xmx128m"));
        cmd.addAll(List.of(args));
        Path log = Files.createTempFile(cwd,"child-",".log");
        var p = new ProcessBuilder(cmd).directory(cwd.toFile()).redirectErrorStream(true).redirectOutput(log.toFile()).start();
        try {
            if (!p.waitFor(15,TimeUnit.SECONDS)) throw new IOException("archive program timed out");
            return new Run(p.exitValue(),Files.readString(log));
        } finally { if (p.isAlive()) p.destroyForcibly(); }
    }
}
