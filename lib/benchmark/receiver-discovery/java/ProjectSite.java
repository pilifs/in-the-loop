import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.IdentityHashMap;
import java.util.Map;
import jdk.internal.org.objectweb.asm.*;
import jdk.internal.org.objectweb.asm.tree.*;

/** Add observations to a copy. All PC selections refer to the input class before projection. */
public final class ProjectSite implements Opcodes {
    static final String STATE = "org/intheloop/observation/SiteState";
    static final String HEAD = "L" + STATE + "$Raised;";
    static InsnList mark(int bit) {
        InsnList code = new InsnList();
        code.add(new IntInsnNode(BIPUSH, bit));
        code.add(new MethodInsnNode(INVOKESTATIC, STATE, "mark", "(I)V", false));
        return code;
    }
    static final Map<String,String> exceptions = Map.of(
        "division-by-zero", "java/lang/ArithmeticException", "null", "java/lang/NullPointerException",
        "bounds", "java/lang/ArrayIndexOutOfBoundsException", "array-store", "java/lang/ArrayStoreException",
        "cast", "java/lang/ClassCastException", "negative-array-size", "java/lang/NegativeArraySizeException");

    static void observeException(MethodNode m, AbstractInsnNode op, String exception) {
        // Each recursive activation remembers its own occurrences, including one later rethrown by a handler.
        int seen = m.maxLocals++;
        InsnList prefix = new InsnList();
        prefix.add(new InsnNode(ACONST_NULL));
        prefix.add(new VarInsnNode(ASTORE, seen));
        LabelNode body = new LabelNode(); prefix.add(body);
        m.instructions.insert(prefix);
        LabelNode start = new LabelNode(), end = new LabelNode(), handler = new LabelNode(), resume = new LabelNode();
        m.instructions.insertBefore(op, start);
        InsnList tail = new InsnList();
        tail.add(end); tail.add(new JumpInsnNode(GOTO, resume)); tail.add(handler);
        tail.add(new InsnNode(DUP)); tail.add(new VarInsnNode(ALOAD, seen));
        tail.add(new MethodInsnNode(INVOKESTATIC, STATE, "raised", "(Ljava/lang/Throwable;" + HEAD + ")" + HEAD, false));
        tail.add(new VarInsnNode(ASTORE, seen));
        // This rethrow is before the original next label and is covered by exactly the original handlers of op.
        tail.add(new InsnNode(ATHROW)); tail.add(resume);
        m.instructions.insert(op, tail);
        m.tryCatchBlocks.add(0, new TryCatchBlockNode(start, end, handler, exception));
        LabelNode finish = new LabelNode(), escape = new LabelNode();
        m.instructions.add(finish); m.instructions.add(escape);
        m.instructions.add(new InsnNode(DUP)); m.instructions.add(new VarInsnNode(ALOAD, seen));
        m.instructions.add(new MethodInsnNode(INVOKESTATIC, STATE, "leaving", "(Ljava/lang/Throwable;" + HEAD + ")V", false));
        m.instructions.add(new InsnNode(ATHROW));
        m.tryCatchBlocks.add(new TryCatchBlockNode(body, finish, escape, "java/lang/Throwable"));
    }

    static void observeBranch(MethodNode m, JumpInsnNode jump) {
        LabelNode taken = new LabelNode(), fall = new LabelNode(), original = jump.label;
        jump.label = taken;
        InsnList edges = mark(8);
        edges.add(new JumpInsnNode(GOTO, fall)); edges.add(taken); edges.add(mark(4));
        edges.add(new JumpInsnNode(GOTO, original)); edges.add(fall);
        m.instructions.insert(jump, edges);
    }

    // An explicit per-activation budget on each original backward edge. A selected fact may
    // never suppress a completeness obligation. Saturation keeps the monitor itself from overflowing.
    static LabelNode counted(MethodNode m, LabelNode destination, int limit, InsnList init, InsnList trampolines) {
        int count = m.maxLocals++;
        init.add(new InsnNode(ICONST_0)); init.add(new VarInsnNode(ISTORE, count));
        LabelNode edge = new LabelNode(), within = new LabelNode();
        trampolines.add(edge); trampolines.add(new VarInsnNode(ILOAD, count)); trampolines.add(new LdcInsnNode(limit));
        trampolines.add(new JumpInsnNode(IF_ICMPLT, within)); trampolines.add(mark(16));
        trampolines.add(new JumpInsnNode(GOTO, destination)); trampolines.add(within);
        trampolines.add(new IincInsnNode(count, 1)); trampolines.add(new JumpInsnNode(GOTO, destination)); return edge;
    }
    static void budgets(MethodNode m, AbstractInsnNode[] original, int limit) {
        var positions = new IdentityHashMap<AbstractInsnNode,Integer>();
        for (int i = 0; i < original.length; i++) positions.put(original[i], i);
        InsnList init = new InsnList(), tails = new InsnList();
        for (var ins : original) {
            int source = positions.get(ins);
            var edges = new IdentityHashMap<LabelNode,LabelNode>();
            java.util.function.UnaryOperator<LabelNode> target = label -> positions.get(label) <= source
                ? edges.computeIfAbsent(label, l -> counted(m, l, limit, init, tails)) : label;
            if (ins instanceof JumpInsnNode j) j.label = target.apply(j.label);
            if (ins instanceof LookupSwitchInsnNode s) { s.dflt = target.apply(s.dflt); s.labels.replaceAll(target); }
            if (ins instanceof TableSwitchInsnNode s) { s.dflt = target.apply(s.dflt); s.labels.replaceAll(target); }
        }
        m.instructions.insert(init); m.instructions.add(tails);
    }

    public static void main(String[] args) throws Exception {
        // input file, expected hash, owner, method, descriptor, ordinal, raw opcode, kind, bound, output
        byte[] raw = Files.readAllBytes(Path.of(args[0]));
        if (!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw)).equals(args[1]))
            throw new IllegalArgumentException("selected class digest changed");
        ClassReader reader = new ClassReader(raw);
        ClassNode cls = new ClassNode(); reader.accept(cls, ClassReader.EXPAND_FRAMES);
        if (!cls.name.equals(args[2])) throw new IllegalArgumentException("selected owner changed");
        MethodNode m = cls.methods.stream().filter(x -> x.name.equals(args[3]) && x.desc.equals(args[4])).findFirst().orElseThrow();
        AbstractInsnNode[] original = m.instructions.toArray();
        var op = java.util.Arrays.stream(original).filter(i -> i.getOpcode() >= 0).skip(Integer.parseInt(args[5])).findFirst().orElseThrow();
        if (op.getOpcode() != Integer.parseInt(args[6])) throw new IllegalArgumentException("selected original opcode changed");
        String kind = args[7];
        if (m.name.startsWith("<")) throw new IllegalArgumentException("constructor/initializer projections are unsupported");
        if (kind.equals("null") && (op instanceof MethodInsnNode || op.getOpcode() == ATHROW))
            throw new IllegalArgumentException("null-receiver check cannot be isolated from a nested or explicit throw");
        budgets(m, original, Integer.parseInt(args[8]));
        if (kind.equals("return") && args.length > 10) {
            if (op.getOpcode() != IRETURN) throw new IllegalArgumentException("expected an int return");
            InsnList checked = new InsnList(); LabelNode equal = new LabelNode();
            checked.add(new InsnNode(DUP)); checked.add(new LdcInsnNode(Integer.parseInt(args[10])));
            checked.add(new JumpInsnNode(IF_ICMPEQ, equal)); checked.add(mark(64)); checked.add(equal);
            m.instructions.insertBefore(op, checked);
        } else if (kind.equals("branch")) observeBranch(m, (JumpInsnNode) op);
        else if (exceptions.containsKey(kind)) observeException(m, op, exceptions.get(kind));
        else if (!kind.equals("return") && !kind.equals("assertion-allocation") && !kind.equals("throw"))
            throw new IllegalArgumentException("unsupported observation " + kind);
        m.instructions.insertBefore(op, mark(1));
        ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_FRAMES);
        cls.accept(writer); Path output = Path.of(args[9]); Files.createDirectories(output.getParent());
        Files.write(output, writer.toByteArray());
    }
}
