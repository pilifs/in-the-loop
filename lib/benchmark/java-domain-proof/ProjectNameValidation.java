import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import jdk.internal.org.objectweb.asm.*;
import jdk.internal.org.objectweb.asm.tree.*;
import static jdk.internal.org.objectweb.asm.Opcodes.*;

/** Extract the consumer of ThreadLocal.get and the actual supplier installed for that field. */
public final class ProjectNameValidation {
    static final String SCHEMA = "org/apache/avro/Schema";
    static final String THREAD_LOCAL = "java/lang/ThreadLocal";
    static final String NAME = "(Ljava/lang/String;)Ljava/lang/String;";
    static final String EXPLICIT = "(Ljava/lang/String;Ljava/lang/Object;)Ljava/lang/String;";

    static MethodNode method(ClassNode type, String name, String desc) {
        List<MethodNode> found = type.methods.stream().filter(m -> m.name.equals(name) && m.desc.equals(desc)).toList();
        if (found.size() != 1) throw new IllegalArgumentException("missing or ambiguous method " + name + desc);
        return found.get(0);
    }

    static AbstractInsnNode previous(AbstractInsnNode at) {
        do { at = at.getPrevious(); } while (at != null && at.getOpcode() < 0);
        return at;
    }

    static MethodNode supplier(ClassNode type, FieldInsnNode field) {
        MethodNode found = null;
        for (AbstractInsnNode insn : method(type, "<clinit>", "()V").instructions) {
            if (!(insn instanceof FieldInsnNode f) || f.getOpcode() != PUTSTATIC
                    || !f.owner.equals(field.owner) || !f.name.equals(field.name) || !f.desc.equals(field.desc)) continue;
            if (found != null || !(previous(f) instanceof MethodInsnNode call) || call.getOpcode() != INVOKESTATIC
                    || !call.owner.equals("org/apache/avro/util/internal/ThreadLocalWithInitial") || !call.name.equals("of")
                    || !call.desc.equals("(Ljava/util/function/Supplier;)Ljava/lang/ThreadLocal;")
                    || !(previous(call) instanceof InvokeDynamicInsnNode indy) || !indy.name.equals("get")
                    || !indy.desc.equals("()Ljava/util/function/Supplier;")
                    || !indy.bsm.getOwner().equals("java/lang/invoke/LambdaMetafactory") || !indy.bsm.getName().equals("metafactory")
                    || indy.bsmArgs.length != 3 || !Type.getMethodType("()Ljava/lang/Object;").equals(indy.bsmArgs[0])
                    || !(indy.bsmArgs[1] instanceof Handle h) || h.getTag() != H_INVOKESTATIC || !h.getOwner().equals(SCHEMA)
                    || !h.getDesc().startsWith("()") || !Type.getMethodType(h.getDesc()).equals(indy.bsmArgs[2]))
                throw new IllegalArgumentException("unexpected supplier for " + f.name);
            found = method(type, h.getName(), h.getDesc());
        }
        if (found == null) throw new IllegalArgumentException("no supplier for " + field.name);
        return found;
    }

    public static void main(String[] args) throws Exception {
        ClassReader original = new ClassReader(Files.readAllBytes(Path.of(args[0])));
        ClassNode type = new ClassNode(ASM9);
        original.accept(type, ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
        MethodNode validate = method(type, "validateName", NAME);
        if (!SCHEMA.equals(type.name) || (validate.access & (ACC_STATIC | ACC_SYNCHRONIZED)) != ACC_STATIC
                || !validate.tryCatchBlocks.isEmpty()) throw new IllegalArgumentException("unexpected validation method");
        AbstractInsnNode first = validate.instructions.getFirst();
        if (!(first instanceof FieldInsnNode f) || f.getOpcode() != GETSTATIC || !f.owner.equals(SCHEMA)
                || !f.name.equals(args[2]) || !f.desc.equals("Ljava/lang/ThreadLocal;")
                || !(f.getNext() instanceof MethodInsnNode get) || get.getOpcode() != INVOKEVIRTUAL
                || !get.owner.equals(THREAD_LOCAL) || !get.name.equals("get") || !get.desc.equals("()Ljava/lang/Object;"))
            throw new IllegalArgumentException("unexpected validation entry");
        // No label in the removed prefix can be a branch target. Padding preserves all original bytecode offsets.
        MethodNode initial = supplier(type, f);
        if ((initial.access & (ACC_STATIC | ACC_SYNCHRONIZED)) != ACC_STATIC || !initial.tryCatchBlocks.isEmpty())
            throw new IllegalArgumentException("unexpected supplier body");
        System.out.println(initial.name + " " + initial.desc);
        validate.instructions.set(f, new VarInsnNode(ALOAD, 1));
        for (int i = 0; i < 5; i++) validate.instructions.insertBefore(get, new InsnNode(NOP));
        validate.instructions.remove(get);
        validate.access = initial.access = ACC_PUBLIC | ACC_STATIC;
        validate.desc = EXPLICIT;
        initial.name = "defaultPolicy";
        ClassWriter out = new ClassWriter(original, ClassWriter.COMPUTE_FRAMES);
        out.visit(type.version, ACC_PUBLIC | ACC_FINAL | ACC_SUPER, "campaign/NameSuffix", null, "java/lang/Object", null);
        initial.accept(out);
        validate.accept(out);
        out.visitEnd();
        Files.write(Path.of(args[1]), out.toByteArray());
    }
}
