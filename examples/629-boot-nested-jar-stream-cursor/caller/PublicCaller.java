import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.jar.JarFile;
import java.util.zip.*;
import org.springframework.boot.loader.jar.NestedJarFile;

public class PublicCaller {
    static final byte[] PAYLOAD = {17, 23, 41, 59, 61, 73, 89};
    static void add(ZipOutputStream archive, String name, byte[] bytes, boolean stored) throws IOException {
        var entry = new ZipEntry(name);
        if (stored) {
            var crc = new CRC32();
            crc.update(bytes);
            entry.setMethod(ZipEntry.STORED);
            entry.setSize(bytes.length);
            entry.setCrc(crc.getValue());
        }
        archive.putNextEntry(entry);
        archive.write(bytes);
        archive.closeEntry();
    }
    static String read(JarFile original, JarFile independent, String name, int skip) throws IOException {
        try (var boot = original.getInputStream(original.getEntry(name)); var jdk = independent.getInputStream(independent.getEntry(name))) {
            if (skip == 1 && (boot.read() != Byte.toUnsignedInt(PAYLOAD[0]) || jdk.read() != Byte.toUnsignedInt(PAYLOAD[0]))) return "wrong-prefix";
            if (skip == 3) { boot.skipNBytes(3); jdk.skipNBytes(3); }
            byte[] tail = boot.readAllBytes(), reference = jdk.readAllBytes();
            boolean content = Arrays.equals(tail, reference) && Arrays.equals(tail, Arrays.copyOfRange(PAYLOAD, skip, PAYLOAD.length));
            if (skip == 0) return Arrays.equals(tail, reference) + ":" + Arrays.equals(tail, PAYLOAD);
            boolean atEnd = skip == 1 ? boot.readAllBytes().length == 0 : boot.read() == -1;
            return content + ":" + atEnd;
        } catch (EOFException e) { return "EOFException"; }
    }
    public static String observe(String[] args) throws Exception {
        Path inner = Files.createTempFile("inner", ".jar"), outer = Files.createTempFile("outer", ".jar");
        try (var z = new ZipOutputStream(Files.newOutputStream(inner))) {
            add(z, "stored", PAYLOAD, true);
            add(z, "deflated", PAYLOAD, false);
        }
        try (var z = new ZipOutputStream(Files.newOutputStream(outer))) { add(z, "lib/sample.jar", Files.readAllBytes(inner), true); }
        try (var boot = new NestedJarFile(outer.toFile(), "lib/sample.jar"); var jdk = new JarFile(inner.toFile())) {
            if (args[0].equals("intent")) return read(boot, jdk, "stored", 1);
            int skip = args[0].equals("challenge") ? 3 : 0;
            return read(boot, jdk, "stored", skip) + "/" + read(boot, jdk, "deflated", skip);
        }
    }
}
