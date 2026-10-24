package net.terminalvalue.contracts;

import java.lang.invoke.MethodType;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.StringJoiner;

/**
 * Derives the contract of a method from its bytecode in three steps, each of which can refuse:
 *
 * <ol>
 *   <li><b>Purity</b> ({@link Purity}): the method is a function of its arguments.
 *   <li><b>Domain</b> ({@link Domains}): its parameters have finitely many values.
 *   <li><b>Execution</b>: run it on every input and record the outcome, a value or an exception.
 * </ol>
 *
 * Together these decide the method's behaviour exactly, which is why the result can serve as a contract: two
 * versions of the code with equal contracts behave identically on every input.
 */
final class Verifier {

    /** The result of deriving a contract: either the contract, or why it cannot be derived. */
    record Derivation(String target, Contract contract, Purity.Result purity, String problem, Class<?> owner) {}

    private final ClassLoader loader;

    Verifier(ClassLoader loader) {
        this.loader = loader;
    }

    Derivation derive(String target) {
        int hash = target.indexOf('#');
        if (hash < 0) {
            return failed(target, "target must be <class>#<method>", null, null);
        }
        Class<?> owner;
        try {
            owner = Class.forName(target.substring(0, hash), false, loader);
        } catch (ClassNotFoundException e) {
            return failed(target, "class not found: " + e.getMessage(), null, null);
        }
        String name = target.substring(hash + 1);
        var candidates = Arrays.stream(owner.getDeclaredMethods())
                .filter(m -> m.getName().equals(name) && !m.isSynthetic())
                .toList();
        if (candidates.size() != 1) {
            return failed(target, "expected one method named " + name + ", found " + candidates.size(), null, owner);
        }
        Method method = candidates.getFirst();
        if (!Modifier.isStatic(method.getModifiers())) {
            return failed(target, "only static methods are supported", null, owner);
        }

        String descriptor = MethodType.methodType(method.getReturnType(), method.getParameterTypes())
                .toMethodDescriptorString();
        var purity = new Purity(loader).analyse(owner, name, descriptor);
        if (!purity.pure()) {
            return failed(target, "not provably pure:\n  " + String.join("\n  ", purity.violations()), purity, owner);
        }

        List<List<Object>> domains = new ArrayList<>();
        var domain = new StringJoiner(" × ");
        try {
            for (Class<?> type : method.getParameterTypes()) {
                var values = Domains.values(type, true);
                domains.add(values);
                domain.add(type.getSimpleName() + " (" + values.size() + ")");
            }
            var inputs = Domains.product(domains);
            method.setAccessible(true);
            Map<String, String> cases = new LinkedHashMap<>();
            for (List<Object> args : inputs) {
                String input = render(name, args);
                String outcome = run(method, args);
                if (!outcome.equals(run(method, args))) {
                    return failed(target, "nondeterministic on " + input, purity, owner);
                }
                cases.put(input, outcome);
            }
            String summary = domain + " = " + inputs.size() + " cases";
            return new Derivation(target, new Contract(target, summary, cases), purity, null, owner);
        } catch (Domains.UnboundedException e) {
            return failed(target, "input domain is not finite: " + e.getMessage(), purity, owner);
        }
    }

    private static String run(Method method, List<Object> args) {
        try {
            return Render.value(method.invoke(null, args.toArray()));
        } catch (InvocationTargetException e) {
            return Render.thrown(e.getCause());
        } catch (IllegalAccessException e) {
            throw new IllegalStateException(e);
        }
    }

    private static String render(String name, List<Object> args) {
        var joiner = new StringJoiner(", ", name + "(", ")");
        args.forEach(arg -> joiner.add(Render.value(arg)));
        return joiner.toString();
    }

    private static Derivation failed(String target, String problem, Purity.Result purity, Class<?> owner) {
        return new Derivation(target, null, purity, problem, owner);
    }

    /** The changed, added and removed cases between a checked-in contract and the code. */
    static List<String> diff(Contract expected, Contract actual) {
        List<String> lines = new ArrayList<>();
        expected.cases().forEach((input, outcome) -> {
            String now = actual.cases().get(input);
            if (now == null) {
                lines.add("  " + input + "\n    removed: this input no longer exists (was " + outcome + ")");
            } else if (!now.equals(outcome)) {
                lines.add("  " + input + "\n    contract: " + outcome + "\n    actual:   " + now);
            }
        });
        actual.cases().forEach((input, outcome) -> {
            if (!expected.cases().containsKey(input)) {
                lines.add("  " + input + "\n    added:    " + outcome);
            }
        });
        return lines;
    }

    static Path sourceFile(Class<?> owner, List<Path> sourceRoots) {
        if (owner == null) {
            return null;
        }
        Class<?> top = owner;
        while (top.getEnclosingClass() != null) {
            top = top.getEnclosingClass();
        }
        String relative = top.getName().replace('.', '/') + ".java";
        return sourceRoots.stream().map(root -> root.resolve(relative)).filter(Files::exists).findFirst().orElse(null);
    }
}
