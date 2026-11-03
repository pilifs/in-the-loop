package net.terminalvalue.contracts;

import java.io.IOException;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

/**
 * Command line:
 *
 * <pre>
 * verify --contracts DIR [--sources DIR...] [--base DIR] [--report DIR]
 * update --contracts DIR [--add CLASS#METHOD]...
 * equivalence --before DIR --after DIR --target CLASS#METHOD [--unchanged-unless EXPR]
 * </pre>
 *
 * The classes under verification must be on the classpath. {@code verify} exits 1 if any contract no longer matches
 * the code or any target cannot be verified; {@code update} rewrites the contracts from the code. {@code equivalence}
 * ({@link Equivalence}) compares two compiled versions of a method with unbounded inputs symbolically.
 */
public final class Main {

    public static void main(String[] args) throws IOException {
        System.exit(run(args, System.out));
    }

    static int run(String[] args, PrintStream out) throws IOException {
        if (args.length > 0 && args[0].equals("equivalence")) {
            try {
                return Equivalence.run(args, out);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return 2;
            }
        }
        if (args.length == 0 || !(args[0].equals("verify") || args[0].equals("update"))) {
            out.println("usage: verify|update --contracts DIR [--add CLASS#METHOD] [--sources DIR] [--base DIR] [--report DIR]");
            out.println("       equivalence --before DIR --after DIR --target CLASS#METHOD [--unchanged-unless EXPR]"
                    + " [--classpath PATH] [--work DIR] [--report DIR] [--sources DIR] [--base DIR]");
            return 2;
        }
        boolean update = args[0].equals("update");
        Path contracts = null;
        Path report = null;
        Path base = Path.of("").toAbsolutePath();
        List<Path> sources = new ArrayList<>();
        List<Path> classes = new ArrayList<>();
        List<String> added = new ArrayList<>();
        String module = "module";
        for (int i = 1; i + 1 < args.length; i += 2) {
            switch (args[i]) {
                case "--contracts" -> contracts = Path.of(args[i + 1]);
                case "--report" -> report = Path.of(args[i + 1]);
                case "--base" -> base = Path.of(args[i + 1]).toAbsolutePath();
                case "--sources" -> sources.add(Path.of(args[i + 1]).toAbsolutePath());
                case "--classes" -> classes.add(Path.of(args[i + 1]).toAbsolutePath());
                case "--module" -> module = args[i + 1];
                case "--add" -> added.add(args[i + 1]);
                default -> throw new IllegalArgumentException("unknown option " + args[i]);
            }
        }
        if (contracts == null) {
            throw new IllegalArgumentException("--contracts is required");
        }

        // Every target: those with a contract file, plus any being added. The module's capability contract, if any,
        // is a target of its own kind.
        Map<String, Path> targets = new LinkedHashMap<>();
        Path capabilities = contracts.resolve(Capabilities.FILE_NAME);
        boolean checkCapabilities = Files.exists(capabilities) || added.remove("capabilities");
        if (Files.isDirectory(contracts)) {
            try (Stream<Path> files = Files.list(contracts)) {
                for (Path file : files.filter(f -> f.toString().endsWith(".contract")).sorted().toList()) {
                    if (!file.getFileName().toString().equals(Capabilities.FILE_NAME)) {
                        targets.put(Contract.read(file).target(), file);
                    }
                }
            }
        }
        for (String target : added) {
            targets.putIfAbsent(target, contracts.resolve(Contract.fileName(target)));
        }
        if (targets.isEmpty() && !checkCapabilities) {
            out.println("No contracts in " + contracts + ". Add one with: updateContracts -Ptarget=<class>#<method>,"
                    + " or the module's capability contract with: updateContracts -Ptarget=capabilities");
            return 0;
        }

        List<Sarif.Finding> findings = new ArrayList<>();
        if (checkCapabilities) {
            checkCapabilities(out, update, capabilities, classes, module, sources, base, findings);
        }
        var verifier = new Verifier(Main.class.getClassLoader());
        for (var entry : targets.entrySet()) {
            var derivation = verifier.derive(entry.getKey());
            Path source = Verifier.sourceFile(derivation.owner(), sources);
            String uri = source == null ? null : base.relativize(source).toString().replace('\\', '/');
            int line = derivation.purity() == null ? 1 : derivation.purity().firstLine();

            if (derivation.problem() != null) {
                String message = entry.getKey() + " cannot be verified: " + derivation.problem();
                out.println("✗ " + message);
                findings.add(new Sarif.Finding("unverifiable", message, uri, line));
                continue;
            }
            Contract actual = derivation.contract();
            String stats = actual.cases().size() + " cases, " + derivation.purity().reached().size()
                    + " methods proven pure, trusting " + String.join(", ", derivation.purity().trustedCalls());
            if (update) {
                actual.write(entry.getValue());
                out.println("✓ wrote " + entry.getValue() + " (" + stats + ")");
                continue;
            }
            if (!Files.exists(entry.getValue())) {
                String message = entry.getKey() + " has no contract file " + entry.getValue();
                out.println("✗ " + message);
                findings.add(new Sarif.Finding("behaviour-changed", message, uri, line));
                continue;
            }
            var diff = Verifier.diff(Contract.read(entry.getValue()), actual);
            if (diff.isEmpty()) {
                out.println("✓ " + entry.getKey() + " matches its contract (" + stats + ")");
            } else {
                String message = "Behaviour of " + entry.getKey() + " differs from its contract in " + diff.size()
                        + " of " + actual.cases().size() + " cases:\n" + String.join("\n", diff);
                out.println("✗ " + message);
                out.println("  (" + stats + ")");
                findings.add(new Sarif.Finding("behaviour-changed", message, uri, line));
            }
        }
        if (report != null) {
            Sarif.write(report.resolve("contracts.sarif"), findings);
        }
        if (findings.stream().anyMatch(f -> f.ruleId().equals("behaviour-changed"))) {
            out.println();
            out.println("If a change is intended, run `./gradlew updateContracts` and commit the contract with the code."
                    + " The contract diff then shows reviewers exactly which behaviour changed.");
        }
        if (findings.stream().anyMatch(f -> f.ruleId().equals("unverifiable"))) {
            out.println();
            out.println("A method that cannot be verified has no contract. Move the impure or unbounded part out of it,"
                    + " or pass it in as a parameter, so that the method is a pure function of finite inputs again.");
        }
        if (findings.stream().anyMatch(f -> f.ruleId().equals("capability-changed"))) {
            out.println();
            out.println("If the module is meant to have this capability, run `./gradlew updateContracts` and commit the"
                    + " contract with the code. The contract diff then shows reviewers the new power and where it is used.");
        }
        if (!findings.isEmpty()) {
            return 1;
        }
        return 0;
    }

    private static void checkCapabilities(PrintStream out, boolean update, Path file, List<Path> classes, String module,
                                          List<Path> sources, Path base, List<Sarif.Finding> findings) throws IOException {
        if (classes.isEmpty()) {
            throw new IllegalArgumentException("--classes DIR is required for the capability contract");
        }
        var report = Capabilities.analyse(classes);
        String stats = report.classes() + " classes, " + report.methods() + " methods, "
                + report.uses().values().stream().mapToInt(s -> s.size()).sum() + " capability uses, "
                + report.libraries().size() + " libraries";
        if (update) {
            Capabilities.write(file, report, module);
            out.println("✓ wrote " + file + " (" + stats + ")");
            return;
        }
        var diff = Capabilities.diff(Capabilities.read(file), Capabilities.entries(report));
        if (diff.isEmpty()) {
            out.println("✓ module " + module + " matches its capability contract (" + stats + ")");
            return;
        }
        String message = "Capabilities of module " + module + " differ from its contract:\n" + String.join("\n", diff);
        out.println("✗ " + message);
        out.println("  (" + stats + ")");
        // Anchor the finding to the first added use, when there is one.
        var added = report.uses().values().stream().flatMap(s -> s.stream())
                .filter(u -> diff.contains("  added " + u.capability() + ": " + u.text()))
                .findFirst();
        String uri = null;
        int line = 1;
        if (added.isPresent()) {
            String relative = added.get().callerClass().replaceAll("\\$.*", "") + ".java";
            for (Path root : sources) {
                if (Files.exists(root.resolve(relative))) {
                    uri = base.relativize(root.resolve(relative)).toString().replace('\\', '/');
                    line = Math.max(1, added.get().line());
                }
            }
        }
        findings.add(new Sarif.Finding("capability-changed", message, uri, line));
    }
}
