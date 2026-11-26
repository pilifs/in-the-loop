import org.junit.jupiter.api.*;
import org.junit.platform.engine.*;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.launcher.*;
import org.junit.platform.launcher.core.*;
import org.junit.platform.suite.api.*;

import java.util.*;
import java.util.stream.Stream;

public class PublicCaller {
    @Suite
    @SelectClasses(Factory.class)
    public static class SelectedSuite {}

    static boolean nested, empty;

    public static class Factory {
        @TestFactory
        Stream<DynamicNode> children() {
            Stream<DynamicNode> leaves =
                    empty
                            ? Stream.empty()
                            : Stream.of(
                                    DynamicTest.dynamicTest("A", () -> {}),
                                    DynamicTest.dynamicTest("B", () -> {}));
            return nested ? Stream.of(DynamicContainer.dynamicContainer("group", leaves)) : leaves;
        }
    }

    static String run(boolean container, boolean noLeaves) {
        nested = container;
        empty = noLeaves;
        List<String> names = new ArrayList<>(), suites = new ArrayList<>();
        Set<String> ids = new HashSet<>();
        var listener =
                new TestExecutionListener() {
                    public void executionFinished(TestIdentifier id, TestExecutionResult result) {
                        if (id.isTest()) {
                            names.add(
                                    result.getStatus() == TestExecutionResult.Status.SUCCESSFUL
                                            ? id.getDisplayName()
                                            : id.getDisplayName() + "=" + result.getStatus());
                            ids.add(id.getUniqueId());
                        }
                        if (id.getUniqueIdObject().getLastSegment().getType().equals("suite"))
                            suites.add(
                                    result.getStatus()
                                            + result.getThrowable()
                                                    .map(t -> "/" + t.getClass().getSimpleName())
                                                    .orElse(""));
                    }
                };
        var request =
                LauncherDiscoveryRequestBuilder.request()
                        .selectors(DiscoverySelectors.selectClass(SelectedSuite.class))
                        .filters(EngineFilter.includeEngines("junit-platform-suite"))
                        .build();
        LauncherFactory.create().execute(request, listener);
        Collections.sort(names);
        return "leaves=" + names + ",unique=" + ids.size() + ",suite=" + String.join(",", suites);
    }

    public static String observe(String[] a) {
        return a[0].equals("challenge")
                ? run(true, false) + " / " + run(true, true)
                : run(false, a[0].equals("control"));
    }
}
