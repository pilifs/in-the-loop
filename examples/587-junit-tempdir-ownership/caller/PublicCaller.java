import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.*;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.launcher.core.*;
import org.junit.platform.launcher.listeners.*;

import java.nio.file.*;
import java.util.*;

public class PublicCaller {
    static boolean reverse;
    static final Map<String, Path> paths = new LinkedHashMap<>();

    public static class OwnerOrder implements MethodOrderer {
        public void orderMethods(MethodOrdererContext ctx) {
            ctx.getMethodDescriptors()
                    .sort(
                            (x, y) ->
                                    (reverse ? -1 : 1)
                                            * x.getMethod()
                                                    .getName()
                                                    .compareTo(y.getMethod().getName()));
        }
    }

    @TestMethodOrder(OwnerOrder.class)
    public static class Owners {
        @Test
        void failing(@TempDir(cleanup = CleanupMode.ON_SUCCESS) Path p) throws Exception {
            mark("failed", "F", p);
            Assertions.fail("deliberate owner failure");
        }

        @Test
        void passing(@TempDir(cleanup = CleanupMode.ON_SUCCESS) Path p) throws Exception {
            mark("passed", "P", p);
        }
    }

    public static class Passing {
        @Test
        void passing(@TempDir(cleanup = CleanupMode.ON_SUCCESS) Path p) throws Exception {
            mark("passed", "P", p);
        }
    }

    static void mark(String owner, String marker, Path path) throws Exception {
        paths.put(owner, path);
        Files.writeString(path.resolve("owner"), marker);
    }

    static String marker(String owner) throws Exception {
        Path p = Objects.requireNonNull(paths.get(owner));
        return Files.exists(p) ? Files.readString(p.resolve("owner")) : "absent";
    }

    static String run(boolean control, boolean reversed) throws Exception {
        reverse = reversed;
        paths.clear();
        var listener = new SummaryGeneratingListener();
        var request =
                LauncherDiscoveryRequestBuilder.request()
                        .selectors(
                                DiscoverySelectors.selectClass(
                                        control ? Passing.class : Owners.class))
                        .configurationParameter("junit.jupiter.execution.parallel.enabled", "false")
                        .build();
        LauncherFactory.create().execute(request, listener);
        var summary = listener.getSummary();
        List<String> expectedOrder =
                control
                        ? List.of("passed")
                        : reversed ? List.of("passed", "failed") : List.of("failed", "passed");
        if (!new ArrayList<>(paths.keySet()).equals(expectedOrder))
            throw new AssertionError("owner execution order " + paths.keySet());
        if (!control
                && summary.getFailures().stream()
                        .noneMatch(
                                f ->
                                        "deliberate owner failure"
                                                .equals(f.getException().getMessage())))
            throw new AssertionError("expected owner failure missing");
        return summary.getTestsFailedCount()
                + "/"
                + summary.getTestsSucceededCount()
                + (control ? "" : ",failed=" + marker("failed"))
                + ",passed="
                + marker("passed");
    }

    public static String observe(String[] a) throws Exception {
        return a[0].equals("challenge")
                ? run(false, false) + " / " + run(false, true)
                : run(a[0].equals("control"), false);
    }
}
