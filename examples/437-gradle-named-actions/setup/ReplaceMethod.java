import java.nio.file.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

public class ReplaceMethod {
    static ClassNode read(Path p) throws Exception {
        var node = new ClassNode();
        new ClassReader(Files.readAllBytes(p)).accept(node, 0);
        return node;
    }
    static MethodNode namedAction(ClassNode node) {
        var methods = node.methods.stream().filter(m -> m.name.equals("wrap")
                && m.desc.equals("(Lorg/gradle/api/Action;Ljava/lang/String;)Lorg/gradle/api/internal/tasks/InputChangesAwareTaskAction;")).toList();
        if (methods.size() != 1) throw new IllegalStateException("expected one named action method");
        return methods.get(0);
    }
    public static void main(String[] args) throws Exception {
        var baseline = read(Path.of(args[0]));
        var pinned = read(Path.of(args[1]));
        if (!baseline.name.equals(pinned.name)) throw new IllegalArgumentException("different provider");
        baseline.methods.set(baseline.methods.indexOf(namedAction(baseline)), namedAction(pinned));
        var writer = new ClassWriter(0);
        baseline.accept(writer);
        Files.write(Path.of(args[2]), writer.toByteArray());
    }
}
