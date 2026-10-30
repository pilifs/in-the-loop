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
 * </pre>
 *
 * The classes under verification must be on the classpath. {@code verify} exits 1 if any contract no longer matches
 * the code or any target cannot be verified; {@code update} rewrites the contracts from the code.
 */
public final class Main {

    public static void main(String[] args) throws IOException {
        System.exit(run(args, System.out));
    }

    static int run(String[] args, PrintStream out) throws IOException {
        if (args.length == 0 || !(args[0].equals("verify") || args[0].equals("update"))) {
            out.println("usage: verify|update --contracts DIR [--add CLASS#METHOD] [--sources DIR] [--base DIR] [--report DIR]");
            return 2;
        }
        boolean update = args[0].equals("update");
        Path contracts = null;
        Path report = null;
        Path base = Path.of("").toAbsolutePath();
        List<Path> sources = new ArrayList<>();
        List<String> added = new ArrayList<>();
        for (int i = 1; i + 1 < args.length; i += 2) {
            switch (args[i]) {
                case "--contracts" -> contracts = Path.of(args[i + 1]);
                case "--report" -> report = Path.of(args[i + 1]);
                case "--base" -> base = Path.of(args[i + 1]).toAbsolutePath();
                case "--sources" -> sources.add(Path.of(args[i + 1]).toAbsolutePath());
                case "--add" -> added.add(args[i + 1]);
                default -> throw new IllegalArgumentException("unknown option " + args[i]);
            }
        }
        if (contracts == null) {
            throw new IllegalArgumentException("--contracts is required");
        }

        // Every target: those with a contract file, plus any being added.
        Map<String, Path> targets = new LinkedHashMap<>();
        if (Files.isDirectory(contracts)) {
            try (Stream<Path> files = Files.list(contracts)) {
                for (Path file : files.filter(f -> f.toString().endsWith(".contract")).sorted().toList()) {
                    targets.put(Contract.read(file).target(), file);
                }
            }
        }
        for (String target : added) {
            targets.putIfAbsent(target, contracts.resolve(Contract.fileName(target)));
        }
        if (targets.isEmpty()) {
            out.println("No contracts in " + contracts + ". Add one with: updateContracts -Ptarget=<class>#<method>");
            return 0;
        }

        var verifier = new Verifier(Main.class.getClassLoader());
        List<Sarif.Finding> findings = new ArrayList<>();
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
        if (!findings.isEmpty()) {
            return 1;
        }
        return 0;
    }
}
