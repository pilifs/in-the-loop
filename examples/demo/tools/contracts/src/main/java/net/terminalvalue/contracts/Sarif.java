package net.terminalvalue.contracts;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * Findings as SARIF 2.1.0, which GitHub code scanning and SonarQube ({@code sonar.sarifReportPaths}) both import.
 * Written by hand to keep the tool free of dependencies.
 */
final class Sarif {

    record Finding(String ruleId, String message, String uri, int line) {}

    private static final String[][] RULES = {
        {"behaviour-changed", "The code no longer matches its behavioural contract."},
        {"unverifiable", "The method cannot be verified: it is not pure, or its inputs are not finite."},
        {"capability-changed", "The module's bytecode reaches a capability, or a library, that its contract does not list."},
    };

    private Sarif() {}

    static void write(Path file, List<Finding> findings) throws IOException {
        List<String> rules = new ArrayList<>();
        for (String[] rule : RULES) {
            rules.add("{\"id\":" + json(rule[0]) + ",\"shortDescription\":{\"text\":" + json(rule[1]) + "}}");
        }
        List<String> results = new ArrayList<>();
        for (Finding f : findings) {
            String location = f.uri() == null
                    ? ""
                    : ",\"locations\":[{\"physicalLocation\":{\"artifactLocation\":{\"uri\":" + json(f.uri())
                            + "},\"region\":{\"startLine\":" + Math.max(1, f.line()) + "}}}]";
            results.add("{\"ruleId\":" + json(f.ruleId()) + ",\"level\":\"error\",\"message\":{\"text\":"
                    + json(f.message()) + "}" + location + "}");
        }
        String sarif = "{\"version\":\"2.1.0\",\"$schema\":\"https://json.schemastore.org/sarif-2.1.0.json\","
                + "\"runs\":[{\"tool\":{\"driver\":{\"name\":\"contract-verifier\",\"rules\":["
                + String.join(",", rules) + "]}},\"results\":[" + String.join(",", results) + "]}]}\n";
        Files.createDirectories(file.getParent());
        Files.writeString(file, sarif);
    }

    private static String json(String s) {
        var out = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        return out.append('"').toString();
    }
}
