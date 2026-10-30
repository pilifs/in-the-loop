package net.terminalvalue.contracts;

import java.io.IOException;
import java.io.InputStream;
import java.lang.classfile.ClassFile;
import java.lang.classfile.ClassModel;
import java.lang.classfile.CodeElement;
import java.lang.classfile.MethodModel;
import java.lang.classfile.Opcode;
import java.lang.classfile.instruction.FieldInstruction;
import java.lang.classfile.instruction.InvokeDynamicInstruction;
import java.lang.classfile.instruction.InvokeInstruction;
import java.lang.classfile.instruction.LineNumber;
import java.lang.constant.DirectMethodHandleDesc;
import java.lang.reflect.AccessFlag;
import java.lang.reflect.Modifier;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.TreeSet;

/**
 * Proves, from bytecode, that a method is a pure function of its arguments: running it twice on equal arguments gives
 * equal results, and it changes nothing outside the objects it creates. Without that, executing every input would
 * prove nothing.
 *
 * <p>The analysis walks every application method the target can reach, following virtual calls through sealed
 * hierarchies (a closed world) and rejecting calls whose implementations it cannot enumerate. In those methods it
 * rejects: writes to static fields; reads of mutable static fields; writes to fields outside constructors; native
 * methods; and calls into the JDK that are not on a small list of APIs known to be pure. That list is the trusted base.
 *
 * <p>Known gaps of this POC: stores into arrays and collections that the method did not create are not tracked.
 */
final class Purity {

    record Result(Set<String> reached, Set<String> trustedCalls, List<String> violations, int firstLine) {
        boolean pure() {
            return violations.isEmpty();
        }
    }

    private record Ref(String owner, String name, String descriptor) {
        @Override
        public String toString() {
            return owner.replace('/', '.') + "." + name;
        }
    }

    private final ClassLoader loader;
    private final Map<String, Optional<ClassModel>> models = new HashMap<>();

    Purity(ClassLoader loader) {
        this.loader = loader;
    }

    Result analyse(Class<?> owner, String name, String descriptor) {
        var root = new Ref(internal(owner), name, descriptor);
        Set<Ref> reached = new LinkedHashSet<>();
        Set<String> trusted = new TreeSet<>();
        List<String> violations = new ArrayList<>();
        Deque<Ref> work = new ArrayDeque<>(List.of(root));
        int firstLine = 0;
        while (!work.isEmpty()) {
            Ref ref = work.pop();
            if (!reached.add(ref)) {
                continue;
            }
            MethodModel method = declared(ref).orElse(null);
            if (method == null) {
                violations.add(ref + ": no bytecode found");
                continue;
            }
            if (method.flags().has(AccessFlag.NATIVE)) {
                violations.add(ref + " is native");
                continue;
            }
            var code = method.code();
            if (code.isEmpty()) {
                continue; // abstract: its implementations were enqueued by the dispatch
            }
            boolean constructor = ref.name().equals("<init>");
            for (CodeElement element : code.get()) {
                switch (element) {
                    case LineNumber line -> {
                        if (ref.equals(root) && firstLine == 0) {
                            firstLine = line.line();
                        }
                    }
                    case FieldInstruction field -> checkField(ref, field, constructor, trusted, violations);
                    case InvokeInstruction call -> {
                        var target = new Ref(call.owner().asInternalName(), call.name().stringValue(), call.type().stringValue());
                        boolean virtual = call.opcode() == Opcode.INVOKEVIRTUAL || call.opcode() == Opcode.INVOKEINTERFACE;
                        dispatch(ref, target, virtual, work, trusted, violations);
                    }
                    case InvokeDynamicInstruction indy -> checkIndy(ref, indy, work, trusted, violations);
                    default -> {}
                }
            }
        }
        var names = new TreeSet<String>();
        reached.forEach(r -> names.add(r.toString()));
        return new Result(names, trusted, violations, firstLine);
    }

    private void checkField(
            Ref in, FieldInstruction field, boolean constructor, Set<String> trusted, List<String> violations) {
        String where = field.owner().asInternalName() + "." + field.name().stringValue();
        switch (field.opcode()) {
            case PUTSTATIC -> violations.add(in + " writes static field " + where.replace('/', '.'));
            case PUTFIELD -> {
                if (!constructor) {
                    violations.add(in + " writes field " + where.replace('/', '.') + " outside a constructor");
                }
            }
            case GETSTATIC -> {
                Class<?> owner = load(field.owner().asInternalName());
                if (owner == null || !isApplication(owner)) {
                    violations.add(in + " reads JDK static field " + where.replace('/', '.'));
                } else if (!isFinalField(owner, field.name().stringValue())) {
                    violations.add(in + " reads mutable static field " + where.replace('/', '.'));
                }
            }
            default -> {}
        }
    }

    private void checkIndy(
            Ref in, InvokeDynamicInstruction indy, Deque<Ref> work, Set<String> trusted, List<String> violations) {
        DirectMethodHandleDesc bootstrap = indy.bootstrapMethod();
        String owner = bootstrap.owner().descriptorString();
        switch (owner) {
            case "Ljava/lang/runtime/SwitchBootstraps;",
                    "Ljava/lang/runtime/ObjectMethods;",
                    "Ljava/lang/invoke/StringConcatFactory;" ->
                trusted.add(owner.substring(1, owner.length() - 1).replace('/', '.') + "." + bootstrap.methodName());
            case "Ljava/lang/invoke/LambdaMetafactory;" -> {
                if (indy.bootstrapArgs().get(1) instanceof DirectMethodHandleDesc impl) {
                    String implOwner = impl.owner().descriptorString();
                    work.push(new Ref(
                            implOwner.substring(1, implOwner.length() - 1), impl.methodName(), impl.lookupDescriptor()));
                } else {
                    violations.add(in + " creates a lambda with an unknown implementation");
                }
            }
            default -> violations.add(in + " uses invokedynamic with bootstrap " + owner);
        }
    }

    /** Enqueues every implementation a call can reach, or records why it cannot be enumerated. */
    private void dispatch(
            Ref in, Ref call, boolean virtual, Deque<Ref> work, Set<String> trusted, List<String> violations) {
        if (call.owner().startsWith("[")) {
            trusted.add("array." + call.name()); // clone() of an array
            return;
        }
        Class<?> owner = load(call.owner());
        if (owner == null) {
            violations.add(in + " calls " + call + ", whose class cannot be loaded");
            return;
        }
        if (!isApplication(owner)) {
            checkJdk(in, call, trusted, violations);
            return;
        }
        // The implementation that runs for an instance of the owner itself. It may be inherited from a superclass,
        // possibly a JDK one, such as Enum.ordinal().
        Ref resolved = resolve(call);
        if (resolved == null) {
            if (!virtual) {
                violations.add(in + " calls " + call + ", which cannot be resolved");
                return;
            }
        } else if (isApplication(load(resolved.owner()))) {
            work.push(resolved);
        } else {
            checkJdk(in, resolved, trusted, violations);
        }
        // Overrides in subclasses, for a virtual call.
        if (!virtual || isFinal(owner) || isPrivateOrFinal(resolved)) {
            return;
        }
        if (!owner.isSealed()) {
            violations.add(in + " calls " + call + " virtually on " + owner.getName()
                    + ", which is open to implementations outside the analysed code");
            return;
        }
        for (Class<?> sub : owner.getPermittedSubclasses()) {
            dispatch(in, new Ref(internal(sub), call.name(), call.descriptor()), true, work, trusted, violations);
        }
    }

    private static void checkJdk(Ref in, Ref call, Set<String> trusted, List<String> violations) {
        if (TrustedApi.isPure(call.owner(), call.name())) {
            trusted.add(call.toString());
        } else {
            violations.add(in + " calls " + call + ", which is not known to be pure");
        }
    }

    /** The class that declares the method an instance of {@code call.owner()} runs, or null if it is abstract. */
    private Ref resolve(Ref call) {
        String owner = call.owner();
        while (owner != null) {
            var model = model(owner);
            if (model.isEmpty()) {
                break;
            }
            for (MethodModel m : model.get().methods()) {
                if (m.methodName().equalsString(call.name()) && m.methodType().equalsString(call.descriptor())) {
                    return m.code().isPresent() || m.flags().has(AccessFlag.NATIVE)
                            ? new Ref(owner, call.name(), call.descriptor())
                            : null;
                }
            }
            owner = model.get().superclass().map(e -> e.asInternalName()).orElse(null);
        }
        // Into the JDK: match by name, which is enough to decide trust.
        for (Class<?> c = owner == null ? null : load(owner); c != null; c = c.getSuperclass()) {
            for (var m : c.getDeclaredMethods()) {
                if (m.getName().equals(call.name())) {
                    return new Ref(internal(c), call.name(), call.descriptor());
                }
            }
            if (call.name().equals("<init>")) {
                return new Ref(internal(c), call.name(), call.descriptor());
            }
        }
        return null;
    }

    private Optional<MethodModel> declared(Ref ref) {
        return model(ref.owner()).flatMap(model -> model.methods().stream()
                .filter(m -> m.methodName().equalsString(ref.name()) && m.methodType().equalsString(ref.descriptor()))
                .findFirst());
    }

    /** The bytecode of an application class, or empty for a JDK class. */
    private Optional<ClassModel> model(String internalName) {
        return models.computeIfAbsent(internalName, name -> {
            Class<?> type = load(name);
            if (type == null || !isApplication(type)) {
                return Optional.empty();
            }
            try (InputStream in = loader.getResourceAsStream(name + ".class")) {
                return in == null ? Optional.empty() : Optional.of(ClassFile.of().parse(in.readAllBytes()));
            } catch (IOException e) {
                throw new IllegalStateException(e);
            }
        });
    }

    private boolean isPrivateOrFinal(Ref ref) {
        return ref != null && declared(ref)
                .map(m -> m.flags().has(AccessFlag.PRIVATE) || m.flags().has(AccessFlag.FINAL))
                .orElse(false);
    }

    private Class<?> load(String internalName) {
        try {
            return Class.forName(internalName.replace('/', '.'), false, loader);
        } catch (ClassNotFoundException | LinkageError e) {
            return null;
        }
    }

    private static boolean isApplication(Class<?> type) {
        ClassLoader l = type.getClassLoader();
        return l != null && l != ClassLoader.getPlatformClassLoader();
    }

    private static boolean isFinal(Class<?> type) {
        return Modifier.isFinal(type.getModifiers()) || type.isRecord()
                || (type.isEnum() && !type.isSealed());
    }

    private static boolean isFinalField(Class<?> owner, String name) {
        for (Class<?> c = owner; c != null; c = c.getSuperclass()) {
            try {
                return Modifier.isFinal(c.getDeclaredField(name).getModifiers());
            } catch (NoSuchFieldException e) {
                // keep looking in the superclass
            }
        }
        return false;
    }

    static String internal(Class<?> type) {
        return type.getName().replace('.', '/');
    }
}
