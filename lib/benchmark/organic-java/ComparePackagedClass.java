import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import jdk.internal.org.objectweb.asm.ClassReader;
import jdk.internal.org.objectweb.asm.ClassVisitor;
import jdk.internal.org.objectweb.asm.ClassWriter;
import jdk.internal.org.objectweb.asm.Opcodes;

/** Re-emit both class files through the same visitor so constant-pool and attribute ordering are immaterial. */
public final class ComparePackagedClass {
    static byte[] canonical(Path path) throws Exception {
        ClassReader reader = new ClassReader(Files.readAllBytes(path));
        ClassWriter fresh = new ClassWriter(0);
        reader.accept(new ClassVisitor(Opcodes.ASM9, fresh) {}, ClassReader.EXPAND_FRAMES);
        return fresh.toByteArray();
    }
    public static void main(String[] args) throws Exception {
        byte[] before = canonical(Path.of(args[0])), after = canonical(Path.of(args[1]));
        if (!Arrays.equals(before, after)) throw new IllegalStateException("packaged instructions or class metadata differ");
        System.out.println(java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(before)));
    }
}
