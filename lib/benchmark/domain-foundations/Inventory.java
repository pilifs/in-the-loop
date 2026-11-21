package foundation;

import java.lang.classfile.*;
import java.lang.classfile.attribute.CodeAttribute;
import java.lang.classfile.instruction.*;
import java.lang.reflect.AccessFlag;
import java.nio.file.*;
import java.util.stream.Stream;

/** Offline disassembly of the class bytes selected by the subject JVM. */
public final class Inventory {
    static String member(FieldInstruction f) {
        return f.owner().asInternalName() + "." + f.name().stringValue() + ":" + f.type().stringValue();
    }

    static String producer(Instruction i) {
        if (i instanceof ConstantInstruction c) return i.opcode() + ":literal";
        if (i instanceof FieldInstruction f) return i.opcode() + ":" + member(f);
        if (i instanceof InvokeInstruction c) return i.opcode() + ":" + c.owner().asInternalName()
                + "." + c.name().stringValue() + c.type().stringValue();
        return i == null ? "entry" : i.opcode().toString();
    }

    static void scan(Path file) throws Exception {
        ClassModel cls = ClassFile.of().parse(Files.readAllBytes(file));
        String name = cls.thisClass().asInternalName();
        for (FieldModel f : cls.fields()) {
            if (f.flags().has(AccessFlag.STATIC)) {
                boolean constant = f.findAttribute(Attributes.constantValue()).isPresent();
                System.out.println("declaration\t" + name + "\t" + f.fieldName() + "\t" + f.fieldType() +
                    "\t" + (constant ? "ConstantValue" : "JVM default at preparation"));
            }
        }
        for (MethodModel m : cls.methods()) {
            if (m.code().isEmpty()) continue;
            CodeAttribute code = (CodeAttribute)m.code().get();
            Instruction last = null;
            int pc = 0;
            String location = name + "\t" + m.methodName() + "\t" + m.methodType() + "\t";
            boolean init = m.methodName().equalsString("<clinit>");
            for (CodeElement element : code) {
                if (element instanceof LabelTarget target && code.labelToBci(target.label()) != pc)
                    throw new IllegalStateException("label offset differs in " + location + pc);
                if (!(element instanceof Instruction i)) continue;
                if (i instanceof FieldInstruction f && (i.opcode() == Opcode.PUTSTATIC || init))
                    System.out.println("field\t" + location + pc + "\t" + i.opcode() + "\t" + member(f) + "\t" + producer(last));
                if (init && (i instanceof InvokeInstruction || i instanceof InvokeDynamicInstruction ||
                        i.opcode() == Opcode.ATHROW || i.opcode() == Opcode.MONITORENTER))
                    System.out.println("effect\t" + location + pc + "\t" + producer(i));
                int padded = 1 + (3 - (pc & 3));
                if (i instanceof LookupSwitchInstruction s) pc += padded + 8 + 8 * s.cases().size();
                else if (i instanceof TableSwitchInstruction s) pc += padded + 12 + 4 * (s.highValue() - s.lowValue() + 1);
                else pc += i.sizeInBytes();
                last = i;
            }
            if (pc != code.codeLength()) throw new IllegalStateException("method length differs in " + location);
        }
    }

    public static void main(String[] args) throws Exception {
        try (Stream<Path> files = Files.walk(Path.of(args[0]))) {
            for (Path f : files.filter(p -> p.toString().endsWith(".class")).sorted().toList()) scan(f);
        }
    }
}
