package net.terminalvalue.contracts;

import java.io.IOException;
import java.lang.classfile.ClassFile;
import java.lang.classfile.ClassModel;
import java.lang.classfile.CodeElement;
import java.lang.classfile.MethodModel;
import java.lang.classfile.Opcode;
import java.lang.classfile.instruction.FieldInstruction;
import java.lang.classfile.instruction.InvokeInstruction;
import java.lang.classfile.instruction.LineNumber;
import java.lang.reflect.AccessFlag;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.regex.Pattern;
import java.util.stream.Stream;

/**
 * The capability contract of a module: everything its bytecode can reach beyond pure computation, grouped by
 * capability (the clock, randomness, the file system, the network, processes, reflection, ...), plus the libraries
 * it calls. Like an app's permission manifest, except that it is computed from the compiled code rather than
 * declared, and checked in. The build fails when it changes, so a change that quietly gives a module a new power
 * (a lookup by class name, a DNS query, an environment variable) is reviewed as what it is.
 *
 * <p>The claim is one of absence, and it is sound on a simple argument: on the JVM, every capability is exercised
 * through a JDK entry point, so bytecode that contains no call to the entry points of a capability cannot exercise
 * it. The ways around that argument, reflection, method handles, class loading, native code and serialization, are
 * capabilities on the list themselves, so a module that is clean of them is clean of the rest. What this does not
 * cover is what the module's <em>libraries</em> do with the calls it makes into them; the libraries are listed so
 * that a new one is at least visible.
 */
final class Capabilities {

    /** One call from the module to a JDK entry point, with the capability it exercises. */
    record Use(String capability, String caller, String callee, String callerClass, int line) implements Comparable<Use> {
        String text() {
            return caller + " calls " + callee;
        }

        @Override
        public int compareTo(Use o) {
            return text().compareTo(o.text());
        }
    }

    record Report(int classes, int methods, Map<String, TreeSet<Use>> uses, TreeSet<String> libraries) {

        /** The contract text, one line per use. Libraries are grouped by their first three package segments. */
        List<String> lines() {
            List<String> out = new ArrayList<>();
            for (String capability : CAPABILITIES) {
                var set = uses.getOrDefault(capability, new TreeSet<>());
                if (set.isEmpty()) {
                    out.add(capability + ": none");
                } else {
                    out.add(capability + ":");
                    set.forEach(u -> out.add("  " + u.text()));
                }
            }
            out.add("");
            out.add(libraries.isEmpty() ? "libraries: none" : "libraries:");
            libraries.forEach(l -> out.add("  " + l));
            return out;
        }
    }

    /** A rule: calls to {@code owner} (a regex over the internal name) with a name matching {@code names}. */
    private record Rule(String capability, Pattern owner, Pattern names) {
        boolean matches(String owner, String name) {
            return this.owner.matcher(owner).matches() && names.matcher(name).matches();
        }
    }

    static final String FILE_NAME = "capabilities.contract";

    static final List<String> CAPABILITIES = List.of(
            "clock", "console", "environment", "filesystem", "jndi", "native", "network", "process", "randomness",
            "reflection", "scripting", "serialization", "threads");

    /** JDK types that look like capabilities by package but are plain values: never a capability. */
    private static final Pattern VALUE_TYPES = Pattern.compile("java/net/(URI|URLEncoder|URLDecoder|IDN)");

    /** The JDK entry points of each capability. The first rule whose owner and name both match decides. */
    private static final List<Rule> RULES = List.of(
            rule("native", "java/lang/(System|Runtime)", "load|loadLibrary"),
            rule("native", "java/lang/foreign/.*", ".*"),
            rule("process", "java/lang/ProcessBuilder", ".*"),
            rule("process", "java/lang/ProcessHandle.*", ".*"),
            rule("process", "java/lang/Runtime", "exec|halt|exit|addShutdownHook|removeShutdownHook"),
            rule("process", "java/lang/System", "exit"),
            rule("environment", "java/lang/System", "getenv|getProperty|getProperties|setProperty|setProperties|clearProperty"),
            rule("environment", "java/lang/Runtime", "availableProcessors|totalMemory|freeMemory|maxMemory|gc"),
            rule("clock", "java/lang/System", "currentTimeMillis|nanoTime"),
            rule("clock", "java/time/Clock", "system|systemUTC|systemDefaultZone|tick|tickMillis|tickSeconds|tickMinutes"),
            rule("clock", "java/time/(Instant|LocalDate|LocalDateTime|LocalTime|ZonedDateTime|OffsetDateTime|OffsetTime"
                    + "|Year|YearMonth|MonthDay)", "now"),
            rule("clock", "java/time/ZoneId", "systemDefault"),
            rule("clock", "java/util/Calendar", "getInstance"),
            rule("clock", "java/util/TimeZone", "getDefault"),
            rule("console", "java/lang/System", "console|out|err|in"),
            rule("console", "java/io/Console", ".*"),
            rule("randomness", "java/util/(Random|SplittableRandom|concurrent/ThreadLocalRandom|random/.*)", ".*"),
            rule("randomness", "java/security/SecureRandom", ".*"),
            rule("randomness", "java/lang/(Math|StrictMath)", "random"),
            rule("randomness", "java/util/UUID", "randomUUID"),
            rule("randomness", "java/util/Collections", "shuffle"),
            rule("reflection", "java/lang/Class", "forName|newInstance|getMethods?|getDeclaredMethods?|getConstructors?"
                    + "|getDeclaredConstructors?|getFields?|getDeclaredFields?|getResource|getResourceAsStream|getClassLoader"
                    + "|getRecordComponents|getEnumConstants"),
            rule("reflection", "java/lang/reflect/.*", ".*"),
            rule("reflection", "java/lang/invoke/MethodHandles", "lookup|privateLookupIn|reflectAs"),
            rule("reflection", "java/lang/invoke/MethodHandles\\$Lookup", ".*"),
            rule("reflection", "java/lang/ClassLoader", ".*"),
            rule("reflection", "java/util/ServiceLoader", ".*"),
            rule("reflection", "java/lang/Thread", "getContextClassLoader|setContextClassLoader"),
            rule("serialization", "java/io/(ObjectInputStream|ObjectOutputStream|ObjectInputFilter.*)", ".*"),
            rule("serialization", "java/beans/(XMLDecoder|XMLEncoder)", ".*"),
            rule("jndi", "javax/naming/.*", ".*"),
            rule("scripting", "javax/script/.*", ".*"),
            rule("filesystem", "java/io/(File|FileInputStream|FileOutputStream|FileReader|FileWriter|RandomAccessFile)", ".*"),
            rule("filesystem", "java/nio/file/(Files|FileSystems|Path|Paths)", ".*"),
            rule("filesystem", "java/nio/channels/FileChannel", ".*"),
            rule("filesystem", "java/util/(zip/ZipFile|jar/JarFile)", ".*"),
            rule("network", "java/net/.*", ".*"),
            rule("network", "javax/net/.*", ".*"),
            rule("network", "java/rmi/.*", ".*"),
            rule("network", "java/nio/channels/(Socket|ServerSocket|Datagram|AsynchronousSocket|AsynchronousServerSocket)"
                    + "Channel.*", ".*"),
            rule("threads", "java/lang/Thread", "<init>|start|ofVirtual|ofPlatform|startVirtualThread|sleep|interrupt"
                    + "|setDaemon|join|setPriority"),
            rule("threads", "java/lang/Thread\\$Builder.*", ".*"),
            rule("threads", "java/util/concurrent/(Executors|ForkJoinPool|ThreadPoolExecutor|ScheduledThreadPoolExecutor"
                    + "|Executor|ExecutorService|ScheduledExecutorService)", ".*"),
            rule("threads", "java/util/concurrent/CompletableFuture", ".*Async"),
            rule("threads", "java/util/(Timer|TimerTask)", ".*"));

    private static final Pattern JDK = Pattern.compile("(java|javax|jdk|sun|com/sun)/.*");

    private Capabilities() {}

    private static Rule rule(String capability, String owner, String names) {
        return new Rule(capability, Pattern.compile(owner), Pattern.compile(names));
    }

    /** Analyses every class under {@code dirs}. */
    static Report analyse(List<Path> dirs) throws IOException {
        Map<Path, ClassModel> models = new TreeMap<>();
        Set<String> own = new HashSet<>();
        for (Path dir : dirs) {
            if (!Files.isDirectory(dir)) {
                continue;
            }
            try (Stream<Path> walk = Files.walk(dir)) {
                for (Path file : walk.filter(p -> p.toString().endsWith(".class")).toList()) {
                    ClassModel model = ClassFile.of().parse(file);
                    models.put(file, model);
                    own.add(model.thisClass().asInternalName());
                }
            }
        }
        Map<String, TreeSet<Use>> uses = new TreeMap<>();
        TreeSet<String> libraries = new TreeSet<>();
        int methods = 0;
        for (ClassModel model : models.values()) {
            String className = model.thisClass().asInternalName();
            for (MethodModel method : model.methods()) {
                methods++;
                String caller = className.replace('/', '.') + "." + method.methodName().stringValue();
                if (method.flags().has(AccessFlag.NATIVE)) {
                    add(uses, new Use("native", caller, "a native method", className, 0));
                }
                if (method.code().isEmpty()) {
                    continue;
                }
                int line = 0;
                for (CodeElement element : method.code().get()) {
                    switch (element) {
                        case LineNumber l -> line = l.line();
                        case InvokeInstruction call -> classify(uses, libraries, own, caller, className, line,
                                call.owner().asInternalName(), call.name().stringValue());
                        case FieldInstruction field -> {
                            if (field.opcode() == Opcode.GETSTATIC) {
                                classify(uses, libraries, own, caller, className, line,
                                        field.owner().asInternalName(), field.name().stringValue());
                            }
                        }
                        default -> {}
                    }
                }
            }
        }
        return new Report(models.size(), methods, uses, libraries);
    }

    private static void classify(Map<String, TreeSet<Use>> uses, Set<String> libraries, Set<String> own,
                                 String caller, String callerClass, int line, String owner, String name) {
        if (owner.startsWith("[") || own.contains(owner)) {
            return;
        }
        if (!JDK.matcher(owner).matches()) {
            String[] parts = owner.replace('/', '.').split("\\.");
            libraries.add(String.join(".", List.of(parts).subList(0, Math.min(3, parts.length - 1))));
            return;
        }
        if (VALUE_TYPES.matcher(owner).matches()) {
            return;
        }
        for (Rule rule : RULES) {
            if (rule.matches(owner, name)) {
                add(uses, new Use(rule.capability(), caller, owner.replace('/', '.') + "." + name, callerClass, line));
                return;
            }
        }
    }

    private static void add(Map<String, TreeSet<Use>> uses, Use use) {
        uses.computeIfAbsent(use.capability(), c -> new TreeSet<>()).add(use);
    }

    // The contract file

    static void write(Path file, Report report, String module) throws IOException {
        List<String> lines = new ArrayList<>(List.of(
                "# Capability contract, generated by examples/tools/contracts. Do not edit: run `./gradlew updateContracts`.",
                "# It lists every call from this module's bytecode to a JDK API that reaches beyond pure computation, grouped",
                "# by capability, and the libraries the module calls. The build checks it against the bytecode.",
                "# A change here is a change in what the module is able to do: review it like a new permission.",
                "kind: capabilities",
                "module: " + module + ", " + report.classes() + " classes, " + report.methods() + " methods",
                ""));
        lines.addAll(report.lines());
        Files.createDirectories(file.getParent());
        Files.write(file, lines);
    }

    /** The checked-in uses, as `capability: caller calls callee` and `library: name` lines, for comparison. */
    static TreeSet<String> read(Path file) throws IOException {
        TreeSet<String> entries = new TreeSet<>();
        String section = null;
        for (String line : Files.readAllLines(file)) {
            if (line.isBlank() || line.startsWith("#") || line.startsWith("kind:") || line.startsWith("module:")) {
                continue;
            }
            if (!line.startsWith(" ")) {
                section = line.substring(0, line.indexOf(':'));
                continue;
            }
            entries.add((section.equals("libraries") ? "library" : section) + ": " + line.strip());
        }
        return entries;
    }

    static TreeSet<String> entries(Report report) {
        TreeSet<String> entries = new TreeSet<>();
        report.uses().forEach((capability, set) -> set.forEach(u -> entries.add(capability + ": " + u.text())));
        report.libraries().forEach(l -> entries.add("library: " + l));
        return entries;
    }

    /** Lines describing what the code has that the contract does not, and the reverse. */
    static List<String> diff(Set<String> contract, Set<String> actual) {
        List<String> lines = new ArrayList<>();
        actual.stream().filter(e -> !contract.contains(e)).forEach(e -> lines.add("  added " + e));
        contract.stream().filter(e -> !actual.contains(e)).forEach(e -> lines.add("  removed " + e));
        return lines;
    }
}
