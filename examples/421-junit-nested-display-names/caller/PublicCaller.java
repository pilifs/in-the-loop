import java.util.*;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.launcher.*;
import org.junit.platform.launcher.core.*;

public class PublicCaller {
    static TestIdentifier only(Set<TestIdentifier> children) {
        if (children.size() != 1) throw new IllegalStateException("expected one child, found " + children);
        return children.iterator().next();
    }
    static List<String> discover(Class<?> fixture) {
        var request = LauncherDiscoveryRequestBuilder.request().selectors(DiscoverySelectors.selectClass(fixture)).build();
        TestPlan plan = LauncherFactory.create().discover(request);
        var root = only(plan.getRoots());
        var outer = only(plan.getChildren(root));
        var inner = only(plan.getChildren(outer));
        var leaf = only(plan.getChildren(inner));
        if (!leaf.isTest() || !plan.getChildren(leaf).isEmpty()) throw new AssertionError("leaf");
        return List.of(outer.getDisplayName(), inner.getDisplayName(), leaf.getDisplayName());
    }
    public static String observe(String[] args) {
        return switch (args[0]) {
            case "nested" -> String.join(" | ", discover(inner.OuterA.class));
            case "explicit" -> discover(explicit.OuterA.class).get(2);
            case "rename" -> String.join(" | ", discover(inner.OuterB.class)) + " / " + String.join(" | ", discover(outer.OuterB.class));
            default -> throw new IllegalArgumentException();
        };
    }
}
