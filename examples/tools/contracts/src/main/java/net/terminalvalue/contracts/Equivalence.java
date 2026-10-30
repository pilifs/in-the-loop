package net.terminalvalue.contracts;

import java.io.IOException;
import java.io.PrintStream;
import java.lang.classfile.ClassFile;
import java.lang.classfile.CodeElement;
import java.lang.classfile.MethodModel;
import java.lang.classfile.instruction.LineNumber;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.lang.reflect.Parameter;
import java.net.URI;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.StringJoiner;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.tools.ToolProvider;

/**
 * Regression verification: proves that a method behaves exactly as its previous version on every input, or shows an
 * input where it does not. This is the contract check for methods whose inputs are not finite, such as a {@code long}
 * price and an {@code int} seat count, where running every input is impossible.
 *
 * <p>The statement is "for all inputs, old(x) and new(x) return the same value or throw the same exception",
 * optionally restricted to the inputs the developer did <em>not</em> mean to change. It is proved by bounded model
 * checking of the bytecode with <a href="https://github.com/diffblue/cbmc">JBMC</a>: both versions are compiled into
 * one program (the old one relocated into a {@code before} package), a generated harness asserts the statement, and
 * JBMC turns the harness into a satisfiability problem whose unsatisfiability is the proof. A satisfying assignment is
 * a concrete counterexample, which this tool replays on the JVM to show the two outcomes.
 *
 * <pre>
 * equivalence --before DIR --after DIR --target CLASS#METHOD [--unchanged-unless EXPR] [--classpath PATH]
 *             [--work DIR] [--report DIR] [--sources DIR]... [--base DIR] [--unwind N]
 * </pre>
 */
final class Equivalence {

    /** The exceptions the harness tells apart, most specific first. Anything else is a RuntimeException or an Error. */
    private static final List<String> EXCEPTIONS = List.of(
            "java.lang.NumberFormatException",
            "java.lang.ArithmeticException",
            "java.lang.NullPointerException",
            "java.lang.ArrayIndexOutOfBoundsException",
            "java.lang.StringIndexOutOfBoundsException",
            "java.lang.IndexOutOfBoundsException",
            "java.lang.NegativeArraySizeException",
            "java.lang.ClassCastException",
            "java.lang.IllegalStateException",
            "java.lang.IllegalArgumentException",
            "java.lang.UnsupportedOperationException",
            "java.util.NoSuchElementException",
            "java.util.ConcurrentModificationException",
            "java.lang.RuntimeException",
            "java.lang.Error");

    /** JDK classes whose real bytecode JBMC analyses, instead of the small models it ships. */
    private static final List<String> JDK_CLASSES = List.of("java.lang.Math", "java.lang.StrictMath");

    /** Searched first, so that a counterexample is small enough to read; the last stage is the proof over all inputs. */
    private static final List<String> STAGES = Arrays.asList("[0:20]", "[-100000:100000]", null);

    private static final String HARNESS = "EquivalenceHarness";

    record Options(Path before, Path after, String target, String unchangedUnless, List<Path> classpath, Path work,
                   Path report, List<Path> sources, Path base, int unwind, long timeoutSeconds) {}

    private Equivalence() {}

    static int run(String[] args, PrintStream out) throws IOException, InterruptedException {
        Options options = parse(args);
        Files.createDirectories(options.work());
        int hash = options.target().indexOf('#');
        if (hash < 0) {
            throw new IllegalArgumentException("target must be <class>#<method>");
        }
        String className = options.target().substring(0, hash);
        String methodName = options.target().substring(hash + 1);

        // 1. Both versions in one program: the old one relocated into the package "before".
        Path beforeDir = options.work().resolve("before");
        Relocate.directory(options.before(), beforeDir, "before");

        // 2. The method, from the new version.
        Method method;
        try (var loader = loader(List.of(options.after()), options.classpath())) {
            method = find(loader.loadClass(className), methodName);
        } catch (ClassNotFoundException e) {
            return refuse(out, options, methodName, 1, "class not found: " + className);
        } catch (IllegalArgumentException e) {
            return refuse(out, options, methodName, 1, e.getMessage());
        }
        int line = firstLine(options.after(), className, methodName);
        for (Parameter p : method.getParameters()) {
            if (!p.getType().isPrimitive()) {
                return refuse(out, options, methodName, line, "parameter " + p.getName() + " has type "
                        + p.getType().getName() + "; the symbolic verifier handles primitive parameters only."
                        + " Finite types (enums, booleans, records) are covered by behavioural contracts.");
            }
        }

        // 3. The statement, as a harness JBMC can check.
        Path harnessDir = options.work().resolve("harness");
        Files.createDirectories(harnessDir);
        String source = harness(className, method, options.unchangedUnless());
        Path sourceFile = harnessDir.resolve(HARNESS + ".java");
        Files.writeString(sourceFile, source);
        var javac = ToolProvider.getSystemJavaCompiler();
        List<String> javacArgs = new ArrayList<>(List.of("-d", harnessDir.toString(), "-proc:none", "-nowarn",
                "-cp", path(beforeDir, options.after(), options.classpath()), sourceFile.toString()));
        var errors = new java.io.ByteArrayOutputStream();
        if (javac.run(null, null, errors, javacArgs.toArray(String[]::new)) != 0) {
            return refuse(out, options, methodName, line, "the harness does not compile. Is --unchanged-unless a Java"
                    + " boolean expression over the parameters? javac said:\n" + errors.toString().strip());
        }

        // 4. The JDK bytecode JBMC needs beyond its own models.
        Path jdkDir = options.work().resolve("jdk");
        extractJdkClasses(jdkDir);

        // 5. Prove, or search for a counterexample: small inputs first, then all of them.
        String classpath = path(harnessDir, options.after(), beforeDir, List.of(jdkDir)) + pathSuffix(options.classpath());
        long started = System.nanoTime();
        JbmcResult last = null;
        for (String stage : STAGES) {
            last = jbmc(options, classpath, stage);
            if (last.status() != Status.VERIFIED) {
                break;
            }
        }
        double seconds = (System.nanoTime() - started) / 1e9;
        String domain = Arrays.stream(method.getParameters())
                .map(p -> p.getName() + ": " + p.getType().getName())
                .collect(java.util.stream.Collectors.joining(" × "));
        String restriction = options.unchangedUnless() == null ? "" : " where !(" + options.unchangedUnless() + ")";

        List<Sarif.Finding> findings = new ArrayList<>();
        String uri = sourceUri(options, className);
        switch (last.status()) {
            case VERIFIED -> out.printf(Locale.ROOT,
                    "✓ %s behaves as before on every input%s (%s: %d properties proved over %s in %.1f s;"
                            + " loops unwound %d times with unwinding assertions)%n",
                    options.target(), restriction, last.version(), last.properties(), domain, seconds, options.unwind());
            case VIOLATION -> {
                List<Object> inputs = last.inputs(method);
                String outcomeBefore = replay(List.of(beforeDir), options, "before." + className, methodName, method, inputs);
                String outcomeAfter = replay(List.of(options.after()), options, className, methodName, method, inputs);
                String rendered = render(methodName, method, inputs);
                String message = "Behaviour of " + options.target() + " changed"
                        + (options.unchangedUnless() == null ? "" : " outside the intended inputs (" + options.unchangedUnless() + ")")
                        + ":\n  " + rendered + "\n    before: " + outcomeBefore + "\n    after:  " + outcomeAfter;
                out.println("✗ " + message);
                out.printf(Locale.ROOT, "  (found by %s in %.1f s%s, replayed on the JVM; domain %s)%n", last.version(),
                        seconds, last.stage() == null ? "" : " searching inputs in " + last.stage(), domain);
                findings.add(new Sarif.Finding("behaviour-changed", message, uri, line));
            }
            case UNVERIFIABLE -> {
                String message = options.target() + " cannot be verified: " + last.problem();
                out.println("✗ " + message);
                findings.add(new Sarif.Finding("unverifiable", message, uri, line));
            }
        }
        if (options.report() != null) {
            Sarif.write(options.report().resolve("equivalence.sarif"), findings);
        }
        if (last.status() == Status.VIOLATION) {
            out.println();
            out.println("If the change is intended, say for which inputs with --unchanged-unless, and the verifier proves"
                    + " that nothing else changed. The expression is what a reviewer approves.");
        }
        return findings.isEmpty() ? 0 : 1;
    }

    // The harness

    static String harness(String className, Method method, String unchangedUnless) {
        var params = new StringJoiner(", ");
        var args = new StringJoiner(", ");
        for (Parameter p : method.getParameters()) {
            params.add(p.getType().getName() + " " + p.getName());
            args.add(p.getName());
        }
        Class<?> ret = method.getReturnType();
        boolean isVoid = ret == void.class;
        String type = isVoid ? null : ret.isPrimitive() ? ret.getName() : "Object";
        String zero = isVoid ? null : ret == boolean.class ? "false" : ret.isPrimitive() ? "0" : "null";
        var s = new StringBuilder();
        s.append("/** Generated by the equivalence verifier: asserts that two versions of a method agree. */\n");
        s.append("public final class ").append(HARNESS).append(" {\n");
        s.append("    public static void check(").append(params).append(") {\n");
        if (unchangedUnless != null) {
            s.append("        if (").append(unchangedUnless).append(") { return; } // the inputs the developer meant to change\n");
        }
        for (String side : List.of("before", "after")) {
            String owner = side.equals("before") ? "before." + className : className;
            String var = side.equals("before") ? "a" : "b";
            if (!isVoid) {
                s.append("        ").append(type).append(' ').append(var).append(" = ").append(zero).append(";\n");
            }
            s.append("        int e").append(var).append(" = 0;\n");
            s.append("        try { ").append(isVoid ? "" : var + " = ")
                    .append(owner).append('.').append(method.getName()).append('(').append(args).append("); }");
            for (int i = 0; i < EXCEPTIONS.size(); i++) {
                s.append(" catch (").append(EXCEPTIONS.get(i)).append(" t) { e").append(var).append(" = ").append(i + 1).append("; }");
            }
            s.append('\n');
        }
        s.append("        assert ea == eb");
        if (!isVoid) {
            s.append(" && (ea != 0 || ").append(ret.isPrimitive() ? "a == b" : "java.util.Objects.equals(a, b)").append(')');
        }
        s.append(";\n    }\n}\n");
        return s.toString();
    }

    // JBMC

    enum Status { VERIFIED, VIOLATION, UNVERIFIABLE }

    record JbmcResult(Status status, String version, int properties, Map<Integer, String> rawInputs, String stage,
                      String problem) {

        /** The counterexample's arguments, in parameter order, from the INPUT lines of the trace (keyed by JVM slot). */
        List<Object> inputs(Method method) {
            List<Object> values = new ArrayList<>();
            int slot = 0;
            for (Parameter p : method.getParameters()) {
                String raw = rawInputs.get(slot);
                values.add(parseValue(p.getType(), raw == null ? "0" : raw));
                slot += p.getType() == long.class || p.getType() == double.class ? 2 : 1;
            }
            return values;
        }
    }

    private static JbmcResult jbmc(Options options, String classpath, String stage) throws IOException, InterruptedException {
        List<String> command = new ArrayList<>(List.of(
                "jbmc", HARNESS, "--function", HARNESS + ".check", "--classpath", classpath,
                "--trace", "--throw-runtime-exceptions",
                "--unwind", String.valueOf(options.unwind()), "--unwinding-assertions"));
        if (stage != null) {
            command.addAll(List.of("--java-assume-inputs-interval", stage));
        }
        Path log = options.work().resolve("jbmc" + (stage == null ? "" : "-" + stage.replaceAll("[^0-9-]", "_")) + ".log");
        Process process;
        try {
            process = new ProcessBuilder(command).redirectErrorStream(true).redirectOutput(log.toFile()).start();
        } catch (IOException e) {
            return new JbmcResult(Status.UNVERIFIABLE, "JBMC", 0, Map.of(), stage, "jbmc is not installed (" + e.getMessage() + ")");
        }
        if (!process.waitFor(options.timeoutSeconds(), TimeUnit.SECONDS)) {
            process.destroyForcibly();
            return new JbmcResult(Status.UNVERIFIABLE, "JBMC", 0, Map.of(), stage,
                    "JBMC did not finish within " + options.timeoutSeconds() + " s");
        }
        String output = Files.readString(log);
        Matcher v = Pattern.compile("^JBMC version (\\S+)", Pattern.MULTILINE).matcher(output);
        String version = v.find() ? "JBMC " + v.group(1) : "JBMC";
        Matcher failed = Pattern.compile("\\*\\* (\\d+) of (\\d+) failed").matcher(output);
        if (!failed.find()) {
            String tail = output.lines().filter(l -> !l.isBlank()).reduce((a, b) -> b).orElse("no output");
            return new JbmcResult(Status.UNVERIFIABLE, version, 0, Map.of(), stage, "JBMC produced no verdict: " + tail);
        }
        int properties = Integer.parseInt(failed.group(2));
        if (Integer.parseInt(failed.group(1)) == 0) {
            return new JbmcResult(Status.VERIFIED, version, properties, Map.of(), stage, null);
        }
        List<String> failures = Pattern.compile("^\\[([^\\]]+)\\] .*: FAILURE$", Pattern.MULTILINE).matcher(output)
                .results().map(m -> m.group(1)).toList();
        if (failures.stream().anyMatch(f -> f.contains(".unwind."))) {
            return new JbmcResult(Status.UNVERIFIABLE, version, properties, Map.of(), stage,
                    "a loop was not fully unwound with --unwind " + options.unwind() + " (" + failures.getFirst() + ")");
        }
        if (failures.stream().noneMatch(f -> f.contains(HARNESS + ".check") && f.contains("assertion"))) {
            return new JbmcResult(Status.UNVERIFIABLE, version, properties, Map.of(), stage,
                    "an unexpected property failed: " + String.join(", ", failures));
        }
        Map<Integer, String> inputs = new LinkedHashMap<>();
        Matcher in = Pattern.compile("^\\s*INPUT arg(\\d+)[a-z]: (\\S+)", Pattern.MULTILINE).matcher(output);
        while (in.find()) {
            inputs.put(Integer.parseInt(in.group(1)), in.group(2));
        }
        return new JbmcResult(Status.VIOLATION, version, properties, inputs, stage, null);
    }

    static Object parseValue(Class<?> type, String raw) {
        String s = raw.replaceAll("[LlFfDd]$", "");
        if (type == long.class) {
            return Long.parseLong(s);
        }
        if (type == int.class) {
            return Integer.parseInt(s);
        }
        if (type == short.class) {
            return Short.parseShort(s);
        }
        if (type == byte.class) {
            return Byte.parseByte(s);
        }
        if (type == char.class) {
            return raw.startsWith("'") ? raw.charAt(1) : (char) Integer.parseInt(s);
        }
        if (type == boolean.class) {
            return raw.equals("true") || raw.equals("1");
        }
        if (type == double.class) {
            return Double.parseDouble(s);
        }
        if (type == float.class) {
            return Float.parseFloat(s);
        }
        throw new IllegalArgumentException("not a primitive: " + type);
    }

    // Replaying the counterexample on the JVM

    private static String replay(List<Path> dirs, Options options, String className, String methodName, Method shape,
                                 List<Object> inputs) throws IOException {
        try (var loader = loader(dirs, options.classpath())) {
            Method m = loader.loadClass(className).getDeclaredMethod(methodName, shape.getParameterTypes());
            m.setAccessible(true);
            return Render.value(m.invoke(null, inputs.toArray()));
        } catch (InvocationTargetException e) {
            return Render.thrown(e.getCause());
        } catch (ReflectiveOperationException e) {
            return "<could not replay: " + e + ">";
        }
    }

    private static String render(String methodName, Method method, List<Object> inputs) {
        var joiner = new StringJoiner(", ", methodName + "(", ")");
        Parameter[] params = method.getParameters();
        for (int i = 0; i < params.length; i++) {
            joiner.add(params[i].getName() + "=" + Render.value(inputs.get(i)));
        }
        return joiner.toString();
    }

    // Helpers

    private static Method find(Class<?> owner, String name) {
        var candidates = Arrays.stream(owner.getDeclaredMethods())
                .filter(m -> m.getName().equals(name) && !m.isSynthetic())
                .toList();
        if (candidates.size() != 1) {
            throw new IllegalArgumentException("expected one method named " + name + ", found " + candidates.size());
        }
        if (!Modifier.isStatic(candidates.getFirst().getModifiers())) {
            throw new IllegalArgumentException("only static methods are supported");
        }
        return candidates.getFirst();
    }

    private static int firstLine(Path classes, String className, String methodName) throws IOException {
        Path file = classes.resolve(className.replace('.', '/') + ".class");
        if (!Files.exists(file)) {
            return 1;
        }
        for (MethodModel m : ClassFile.of().parse(file).methods()) {
            if (m.methodName().equalsString(methodName) && m.code().isPresent()) {
                for (CodeElement e : m.code().get()) {
                    if (e instanceof LineNumber l) {
                        return l.line();
                    }
                }
            }
        }
        return 1;
    }

    private static String sourceUri(Options options, String className) {
        String relative = className.replace('.', '/').replaceAll("\\$.*", "") + ".java";
        for (Path root : options.sources()) {
            Path file = root.resolve(relative);
            if (Files.exists(file)) {
                return options.base().relativize(file.toAbsolutePath()).toString().replace('\\', '/');
            }
        }
        return null;
    }

    private static int refuse(PrintStream out, Options options, String method, int line, String problem) throws IOException {
        String message = options.target() + " cannot be verified: " + problem;
        out.println("✗ " + message);
        if (options.report() != null) {
            String uri = sourceUri(options, options.target().substring(0, options.target().indexOf('#')));
            Sarif.write(options.report().resolve("equivalence.sarif"), List.of(new Sarif.Finding("unverifiable", message, uri, line)));
        }
        return 1;
    }

    /** Copies the JDK classes in {@link #JDK_CLASSES} out of the running JDK's image, for JBMC's classpath. */
    private static void extractJdkClasses(Path dir) throws IOException {
        var jrt = FileSystems.getFileSystem(URI.create("jrt:/"));
        for (String name : JDK_CLASSES) {
            String relative = name.replace('.', '/') + ".class";
            Path target = dir.resolve(relative);
            Files.createDirectories(target.getParent());
            Files.copy(jrt.getPath("modules", "java.base", relative), target, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private static URLClassLoader loader(List<Path> dirs, List<Path> classpath) throws IOException {
        List<URL> urls = new ArrayList<>();
        for (Path p : dirs) {
            urls.add(p.toUri().toURL());
        }
        for (Path p : classpath) {
            urls.add(p.toUri().toURL());
        }
        return new URLClassLoader(urls.toArray(URL[]::new), Equivalence.class.getClassLoader());
    }

    private static String path(Path a, Path b, List<Path> rest) {
        return path(a, b, null, rest);
    }

    private static String path(Path a, Path b, Path c, List<Path> rest) {
        var joiner = new StringJoiner(java.io.File.pathSeparator);
        for (Path p : Arrays.asList(a, b, c)) {
            if (p != null) {
                joiner.add(p.toAbsolutePath().toString());
            }
        }
        rest.forEach(p -> joiner.add(p.toAbsolutePath().toString()));
        return joiner.toString();
    }

    private static String pathSuffix(List<Path> classpath) {
        var s = new StringBuilder();
        classpath.forEach(p -> s.append(java.io.File.pathSeparator).append(p.toAbsolutePath()));
        return s.toString();
    }

    static Options parse(String[] args) throws IOException {
        Path before = null, after = null, work = null, report = null;
        Path base = Path.of("").toAbsolutePath();
        String target = null, unchangedUnless = null;
        List<Path> classpath = new ArrayList<>();
        List<Path> sources = new ArrayList<>();
        int unwind = 16;
        long timeout = 600;
        for (int i = 1; i + 1 < args.length; i += 2) {
            switch (args[i]) {
                case "--before" -> before = Path.of(args[i + 1]);
                case "--after" -> after = Path.of(args[i + 1]);
                case "--target" -> target = args[i + 1];
                case "--unchanged-unless" -> unchangedUnless = args[i + 1];
                case "--classpath" -> Arrays.stream(args[i + 1].split(java.io.File.pathSeparator))
                        .filter(s -> !s.isBlank()).map(Path::of).forEach(classpath::add);
                case "--work" -> work = Path.of(args[i + 1]);
                case "--report" -> report = Path.of(args[i + 1]);
                case "--sources" -> sources.add(Path.of(args[i + 1]).toAbsolutePath());
                case "--base" -> base = Path.of(args[i + 1]).toAbsolutePath();
                case "--unwind" -> unwind = Integer.parseInt(args[i + 1]);
                case "--timeout" -> timeout = Long.parseLong(args[i + 1]);
                default -> throw new IllegalArgumentException("unknown option " + args[i]);
            }
        }
        if (before == null || after == null || target == null) {
            throw new IllegalArgumentException("--before, --after and --target are required");
        }
        if (work == null) {
            work = Files.createTempDirectory("equivalence");
        }
        return new Options(before, after, target, unchangedUnless, classpath, work, report, sources, base, unwind, timeout);
    }
}
