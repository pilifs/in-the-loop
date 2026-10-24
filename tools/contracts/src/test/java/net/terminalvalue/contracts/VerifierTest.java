package net.terminalvalue.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class VerifierTest {

    private static final String FIXTURE = "net.terminalvalue.contracts.fixtures.TrafficLight#";

    private final Verifier verifier = new Verifier(getClass().getClassLoader());

    @Test
    void aPureFiniteMethodGetsACompleteContract() {
        var derivation = verifier.derive(FIXTURE + "step");
        assertNull(derivation.problem());
        // Light: 3 + null; Command: Next, Hold(false), Hold(true), null.
        assertEquals(16, derivation.contract().cases().size());
        assertEquals("GREEN", derivation.contract().cases().get("step(RED, Next[])"));
        assertEquals("AMBER", derivation.contract().cases().get("step(RED, Hold[flashing=true])"));
        assertEquals("throws NullPointerException", derivation.contract().cases().get("step(RED, null)"));
    }

    @Test
    void writingStaticStateIsRejected() {
        assertProblem("counting", "writes static field");
    }

    @Test
    void readingTheClockIsRejected() {
        assertProblem("night", "java.lang.System.nanoTime, which is not known to be pure");
    }

    @Test
    void callingAnOpenInterfaceIsRejected() {
        assertProblem("sensed", "open to implementations outside the analysed code");
    }

    @Test
    void anUnboundedDomainIsRejected() {
        assertProblem("doubled", "input domain is not finite");
    }

    @Test
    void diffNamesChangedAddedAndRemovedCases() {
        var before = contract(Map.of("f(A)", "1", "f(B)", "2"));
        var after = contract(Map.of("f(A)", "1", "f(B)", "3", "f(C)", "4"));
        var diff = String.join("\n", Verifier.diff(before, after));
        assertTrue(diff.contains("f(B)\n    contract: 2\n    actual:   3"), diff);
        assertTrue(diff.contains("f(C)\n    added:    4"), diff);
        assertEquals(1, Verifier.diff(after, before).stream().filter(l -> l.contains("removed")).count());
    }

    @Test
    void updateThenVerifyPassesAndDetectsDrift(@TempDir Path dir) throws Exception {
        assertEquals(0, Main.run(new String[] {"update", "--contracts", dir.toString(), "--add", FIXTURE + "step"}, quiet()));
        Path file = dir.resolve("TrafficLight.step.contract");
        assertEquals(0, Main.run(new String[] {"verify", "--contracts", dir.toString()}, quiet()));

        Files.writeString(file, Files.readString(file).replace("=> GREEN", "=> AMBER"));
        var out = new ByteArrayOutputStream();
        assertEquals(1, Main.run(new String[] {"verify", "--contracts", dir.toString(), "--report", dir.toString()},
                new PrintStream(out)));
        assertTrue(out.toString().contains("step(RED, Next[])"), out.toString());
        assertTrue(Files.readString(dir.resolve("contracts.sarif")).contains("behaviour-changed"));
    }

    private void assertProblem(String method, String expected) {
        var derivation = verifier.derive(FIXTURE + method);
        assertTrue(derivation.problem() != null && derivation.problem().contains(expected), derivation.problem());
    }

    private static Contract contract(Map<String, String> cases) {
        return new Contract("t#f", "test", new LinkedHashMap<>(new java.util.TreeMap<>(cases)));
    }

    private static PrintStream quiet() {
        return new PrintStream(new ByteArrayOutputStream());
    }

}
