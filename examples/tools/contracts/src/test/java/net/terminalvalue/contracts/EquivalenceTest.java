package net.terminalvalue.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import javax.tools.ToolProvider;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class EquivalenceTest {

    private static final String PACKAGE = "net.terminalvalue.contracts.fixtures";
    private static final String TARGET = PACKAGE + ".Pricing#total";

    private static final String BEFORE = """
            package net.terminalvalue.contracts.fixtures;
            public final class Pricing {
                public static long total(long priceCents, int seats) {
                    if (priceCents < 0 || seats < 0) throw new IllegalArgumentException("negative");
                    long total = Math.multiplyExact(priceCents, seats);
                    return seats >= 6 ? total - total / 10 : total;
                }
            }
            """;

    /** A refactor that rounds per seat instead of per total: not equivalent. */
    private static final String ROUNDS_DIFFERENTLY = BEFORE.replace(
            "long total = Math.multiplyExact(priceCents, seats);\n        return seats >= 6 ? total - total / 10 : total;",
            "long unit = seats >= 6 ? priceCents - priceCents / 10 : priceCents;\n        return Math.multiplyExact(unit, seats);");

    /** A bigger group discount, with smaller holds untouched. */
    private static final String NEW_TIER = BEFORE.replace(
            "return seats >= 6 ? total - total / 10 : total;",
            "return seats >= 6 ? total - total / 5 : total;");

    @Test
    void relocationRenamesTheClassAndItsReferences(@TempDir Path dir) throws IOException {
        Path classes = compile(dir.resolve("classes"), BEFORE);
        Set<String> moved = Relocate.directory(classes, dir.resolve("out"), "before");
        assertEquals(Set.of(PACKAGE.replace('.', '/') + "/Pricing"), moved);
        assertEquals("Lbefore/a/B;", Relocate.rename("La/B;", Set.of("a/B"), "before"));
        assertEquals("(JLbefore/a/B<La/C;>;)V", Relocate.rename("(JLa/B<La/C;>;)V", Set.of("a/B"), "before"));
        assertEquals("before/a/B", Relocate.rename("a/B", Set.of("a/B"), "before"));
        assertEquals("a/BC", Relocate.rename("a/BC", Set.of("a/B"), "before"));
    }

    @Test
    void theHarnessStatesTheEquivalenceOfBothVersions(@TempDir Path dir) throws Exception {
        Path classes = compile(dir.resolve("classes"), BEFORE);
        try (var loader = new java.net.URLClassLoader(new java.net.URL[] {classes.toUri().toURL()})) {
            var method = loader.loadClass(PACKAGE + ".Pricing").getDeclaredMethod("total", long.class, int.class);
            String harness = Equivalence.harness(PACKAGE + ".Pricing", method, "seats >= 8");
            assertTrue(harness.contains("if (seats >= 8) { return; }"), harness);
            assertTrue(harness.contains("a = before." + PACKAGE + ".Pricing.total(priceCents, seats);"), harness);
            assertTrue(harness.contains("b = " + PACKAGE + ".Pricing.total(priceCents, seats);"), harness);
            assertTrue(harness.contains("assert ea == eb && (ea != 0 || a == b);"), harness);
        }
    }

    @Test
    void aRoundingRefactorIsRefutedWithAReplayedCounterexample(@TempDir Path dir) throws Exception {
        assumeJbmc();
        var out = new ByteArrayOutputStream();
        int exit = run(dir, BEFORE, ROUNDS_DIFFERENTLY, null, out);
        String text = out.toString();
        assertEquals(1, exit, text);
        assertTrue(text.contains("✗ Behaviour of " + TARGET + " changed:"), text);
        assertTrue(text.contains("before: ") && text.contains("after:  "), text);
        assertTrue(Files.readString(dir.resolve("report/equivalence.sarif")).contains("behaviour-changed"));
    }

    @Test
    void aChangeConfinedToItsDeclaredInputsIsProved(@TempDir Path dir) throws Exception {
        assumeJbmc();
        var out = new ByteArrayOutputStream();
        int exit = run(dir, BEFORE, NEW_TIER, "seats >= 6", out);
        assertEquals(0, exit, out.toString());
        assertTrue(out.toString().contains("✓ " + TARGET + " behaves as before on every input where !(seats >= 6)"), out.toString());
    }

    @Test
    void theSameChangeWithoutTheDeclarationIsRefuted(@TempDir Path dir) throws Exception {
        assumeJbmc();
        var out = new ByteArrayOutputStream();
        assertEquals(1, run(dir, BEFORE, NEW_TIER, null, out), out.toString());
        assertTrue(out.toString().contains("before: ") && out.toString().contains("after:  "), out.toString());
    }

    @Test
    void aReferenceParameterIsRefused(@TempDir Path dir) throws Exception {
        String withString = BEFORE.replace("long priceCents, int seats", "String code, int seats")
                .replace("priceCents < 0 || ", "").replace("Math.multiplyExact(priceCents, seats)", "seats");
        var out = new ByteArrayOutputStream();
        assertEquals(1, run(dir, withString, withString, null, out), out.toString());
        assertTrue(out.toString().contains("cannot be verified: parameter code has type java.lang.String"), out.toString());
    }

    private static int run(Path dir, String before, String after, String unchangedUnless, ByteArrayOutputStream out)
            throws Exception {
        List<String> args = new ArrayList<>(List.of("equivalence",
                "--before", compile(dir.resolve("before"), before).toString(),
                "--after", compile(dir.resolve("after"), after).toString(),
                "--target", TARGET,
                "--work", dir.resolve("work").toString(),
                "--report", dir.resolve("report").toString()));
        if (unchangedUnless != null) {
            args.addAll(List.of("--unchanged-unless", unchangedUnless));
        }
        return Main.run(args.toArray(String[]::new), new PrintStream(out));
    }

    private static Path compile(Path dir, String source) throws IOException {
        Path file = dir.resolve("src/Pricing.java");
        Files.createDirectories(file.getParent());
        Files.writeString(file, source);
        Path classes = dir.resolve("classes");
        Files.createDirectories(classes);
        int status = ToolProvider.getSystemJavaCompiler().run(null, null, null,
                "-d", classes.toString(), "-parameters", "-proc:none", file.toString());
        assertEquals(0, status, "fixture does not compile");
        return classes;
    }

    private static void assumeJbmc() {
        boolean installed;
        try {
            installed = new ProcessBuilder("jbmc", "--version").redirectErrorStream(true).start().waitFor() == 0;
        } catch (IOException | InterruptedException e) {
            installed = false;
        }
        assumeTrue(installed, "jbmc is not installed");
    }
}
