package net.terminalvalue.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class CapabilitiesTest {

    private static final String CAPABLE = "net.terminalvalue.contracts.fixtures.Capable";

    @Test
    void findsEachCapabilityAndTheCallSite() throws Exception {
        var report = Capabilities.analyse(List.of(fixtureClasses()));
        var entries = Capabilities.entries(report);
        assertTrue(entries.contains("reflection: " + CAPABLE + ".loadByName calls java.lang.Class.forName"), entries.toString());
        assertTrue(entries.contains("reflection: " + CAPABLE + ".loadByName calls java.lang.Class.getDeclaredConstructor"), entries.toString());
        assertTrue(entries.contains("clock: " + CAPABLE + ".stamp calls java.time.Instant.now"), entries.toString());
        assertTrue(entries.contains("randomness: " + CAPABLE + ".stamp calls java.util.UUID.randomUUID"), entries.toString());
        assertTrue(entries.contains("environment: " + CAPABLE + ".home calls java.lang.System.getenv"), entries.toString());
        assertFalse(entries.stream().anyMatch(e -> e.contains("Capable.pure")), "Math.abs is not a capability");
        // The fixture TrafficLight reads System.nanoTime, and nothing in the fixtures is a library call.
        assertTrue(entries.contains("clock: net.terminalvalue.contracts.fixtures.TrafficLight.night calls java.lang.System.nanoTime"));
        assertTrue(report.libraries().isEmpty(), report.libraries().toString());
        var use = report.uses().get("reflection").first();
        assertTrue(use.line() > 0, "call sites carry their line number");
    }

    @Test
    void writesAndReadsTheContractWithoutLoss(@TempDir Path dir) throws Exception {
        var report = Capabilities.analyse(List.of(fixtureClasses()));
        Path file = dir.resolve(Capabilities.FILE_NAME);
        Capabilities.write(file, report, "fixtures");
        String text = Files.readString(file);
        assertTrue(text.contains("kind: capabilities"), text);
        assertTrue(text.contains("network: none"), text);
        assertTrue(text.contains("reflection:\n  " + CAPABLE + ".loadByName calls java.lang.Class.forName"), text);
        assertEquals(Capabilities.entries(report), Capabilities.read(file));
    }

    @Test
    void diffNamesWhatWasAddedAndRemoved() {
        var contract = new TreeSet<>(Set.of("clock: A.f calls java.time.Instant.now", "library: tools.jackson.databind"));
        var actual = new TreeSet<>(Set.of("clock: A.f calls java.time.Instant.now", "reflection: A.g calls java.lang.Class.forName"));
        assertEquals(List.of("  added reflection: A.g calls java.lang.Class.forName", "  removed library: tools.jackson.databind"),
                Capabilities.diff(contract, actual));
    }

    @Test
    void verifyFailsWhenAModuleGainsACapability(@TempDir Path dir) throws Exception {
        Path classes = fixtureClasses();
        String[] update = {"update", "--contracts", dir.toString(), "--add", "capabilities", "--classes", classes.toString(),
                "--module", "fixtures"};
        assertEquals(0, Main.run(update, quiet()));
        Path file = dir.resolve(Capabilities.FILE_NAME);
        assertEquals(0, Main.run(new String[] {"verify", "--contracts", dir.toString(), "--classes", classes.toString()}, quiet()));

        // Pretend the contract was written before loadByName existed.
        Files.writeString(file, Files.readString(file).replace("  " + CAPABLE + ".loadByName calls java.lang.Class.forName\n", ""));
        var out = new ByteArrayOutputStream();
        int exit = Main.run(new String[] {"verify", "--contracts", dir.toString(), "--classes", classes.toString(),
                "--report", dir.toString()}, new PrintStream(out));
        assertEquals(1, exit, out.toString());
        assertTrue(out.toString().contains("added reflection: " + CAPABLE + ".loadByName calls java.lang.Class.forName"), out.toString());
        assertTrue(Files.readString(dir.resolve("contracts.sarif")).contains("capability-changed"));
    }

    private static Path fixtureClasses() throws URISyntaxException {
        // The compiled fixtures package, inside the test classes directory as Gradle lays it out.
        return Path.of(CapabilitiesTest.class.getProtectionDomain().getCodeSource().getLocation().toURI())
                .resolve("net/terminalvalue/contracts/fixtures");
    }

    private static PrintStream quiet() {
        return new PrintStream(new ByteArrayOutputStream());
    }
}
