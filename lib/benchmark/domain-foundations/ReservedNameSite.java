package foundation;

import java.lang.classfile.*;
import java.lang.classfile.attribute.CodeAttribute;
import java.lang.classfile.instruction.*;
import java.lang.reflect.AccessFlag;
import java.nio.file.*;
import java.util.*;

/** Match the entire independently checked producer to a straight-line interval in the selected Schema class. */
public final class ReservedNameSite {
    record Op(int bci, Instruction instruction) {}
    record Body(ClassModel owner, List<Op> ops) {
        int anchor() {
            int found = -1;
            for (int i = 0; i < ops.size(); i++) {
                if (ops.get(i).instruction() instanceof FieldInstruction f && f.opcode() == Opcode.PUTSTATIC
                        && f.owner().equals(owner.thisClass()) && f.name().equalsString("SCHEMA_RESERVED")) {
                    if (found >= 0) throw new IllegalArgumentException("ambiguous field assignment");
                    found = i;
                }
            }
            if (found < 0) throw new IllegalArgumentException("missing field assignment");
            return found;
        }
        String key(int index) {
            Instruction i = ops.get(index).instruction();
            if (i instanceof ConstantInstruction c) {
                var v = c.constantValue();
                if (v instanceof String s) return "string " + s;
                if (v instanceof Integer n) return "int " + n;
            }
            if (i instanceof NewObjectInstruction n) return i.opcode() + " " + n.className().asInternalName();
            if (i instanceof NewReferenceArrayInstruction n) return i.opcode() + " " + n.componentType().asInternalName();
            if (i instanceof InvokeInstruction m)
                return i.opcode() + " " + m.isInterface() + " " + m.owner().asInternalName() + "." + m.name() + m.type();
            if (i instanceof FieldInstruction f && f.owner().equals(owner.thisClass())
                    && Set.of("SCHEMA_RESERVED", "ENUM_RESERVED").contains(f.name().stringValue())
                    && f.type().equalsString("Ljava/util/Set;")) return i.opcode() + " own." + f.name() + f.type();
            if (i.opcode() == Opcode.DUP || i.opcode() == Opcode.AASTORE || i.opcode() == Opcode.POP)
                return i.opcode().name();
            throw new IllegalArgumentException("unqualified instruction at " + ops.get(index).bci());
        }
    }

    static Body read(Path path) throws Exception {
        ClassModel cls = ClassFile.of().parse(Files.readAllBytes(path));
        for (String name : List.of("SCHEMA_RESERVED", "ENUM_RESERVED")) {
            var fields = cls.fields().stream().filter(f -> f.fieldName().equalsString(name)).toList();
            if (fields.size() != 1 || !fields.getFirst().flags().has(AccessFlag.STATIC)
                    || !fields.getFirst().flags().has(AccessFlag.FINAL)
                    || !fields.getFirst().fieldType().equalsString("Ljava/util/Set;"))
                throw new IllegalArgumentException("unexpected field " + name);
        }
        var init = cls.methods().stream().filter(m -> m.methodName().equalsString("<clinit>")).findFirst().orElseThrow();
        var code = (CodeAttribute) init.code().orElseThrow();
        if (!code.exceptionHandlers().isEmpty()) throw new IllegalArgumentException("initializer has exception handlers");
        var ops = new ArrayList<Op>();
        int pc = 0;
        for (var element : code) {
            if (element instanceof LabelTarget label && code.labelToBci(label.label()) != pc)
                throw new IllegalArgumentException("bytecode offset mismatch");
            if (!(element instanceof Instruction i)) continue;
            if (i instanceof BranchInstruction || i instanceof LookupSwitchInstruction || i instanceof TableSwitchInstruction
                    || i instanceof DiscontinuedInstruction) throw new IllegalArgumentException("initializer has a control-flow edge");
            ops.add(new Op(pc, i));
            pc += i.sizeInBytes();
        }
        if (pc != code.codeLength() || ops.getLast().instruction().opcode() != Opcode.RETURN)
            throw new IllegalArgumentException("incomplete initializer");
        return new Body(cls, ops);
    }

    public static void main(String[] args) throws Exception {
        Body proof = read(Path.of(args[0])), original = read(Path.of(args[1]));
        int start = original.anchor() - proof.anchor(), end = start + proof.ops().size() - 1;
        if (start < 0 || end >= original.ops().size()) throw new IllegalArgumentException("no complete interval");
        for (int i = 0; i < end - start; i++) {
            if (!proof.key(i).equals(original.key(start + i))) throw new IllegalArgumentException("instruction mismatch at " + original.ops().get(start+i).bci());
        }
        System.out.println(original.ops().get(start).bci() + " " + original.ops().get(end).bci() + " " + (end - start));
    }
}
