import java.util.ArrayList;
import java.util.List;
import java.util.TreeMap;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.platform.engine.DiscoverySelector;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.engine.support.descriptor.MethodSource;
import org.junit.platform.launcher.EngineFilter;
import org.junit.platform.launcher.Launcher;
import org.junit.platform.launcher.LauncherDiscoveryRequest;
import org.junit.platform.launcher.TestIdentifier;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;
import org.junit.platform.launcher.listeners.SummaryGeneratingListener;

public class PublicCaller {
    static final List<String> markers = new ArrayList<>();
    static class Base {
        @Nested class A { @Test void check() { markers.add("base"); } }
    }
    static class Sub extends Base {
        @Nested class A { @Test void check() { markers.add("sub"); } }
    }
    static LauncherDiscoveryRequest request(DiscoverySelector selector) {
        return LauncherDiscoveryRequestBuilder.request().selectors(selector)
                .filters(EngineFilter.includeEngines("junit-jupiter"))
                .configurationParameter("junit.jupiter.execution.parallel.enabled", "false").build();
    }
    static String execute(Launcher launcher, LauncherDiscoveryRequest req) {
        markers.clear();
        var listener = new SummaryGeneratingListener();
        launcher.execute(req, listener);
        return markers.stream().sorted().toList() + "/" + listener.getSummary().getTestsSucceededCount()
                + "/" + listener.getSummary().getTotalFailureCount();
    }
    public static String observe(String[] args) {
        var launcher = LauncherFactory.create();
        var req = request(DiscoverySelectors.selectClass(args[0].equals("base") ? Base.class : Sub.class));
        var plan = launcher.discover(req);
        var ids = new TreeMap<String,String>();
        for (var engine : plan.getRoots()) for (TestIdentifier leaf : plan.getDescendants(engine)) {
            if (leaf.isTest()) {
                var src = (MethodSource) leaf.getSource().orElseThrow();
                ids.put(leaf.getUniqueId(), src.getClassName().equals(Base.A.class.getName()) ? "base"
                        : src.getClassName().equals(Sub.A.class.getName()) ? "sub" : src.getClassName());
            }
        }
        var results = new ArrayList<String>();
        if (args[0].equals("reselect")) {
            ids.forEach((id, owner) -> results.add(owner + "=" + execute(LauncherFactory.create(),
                    request(DiscoverySelectors.selectUniqueId(id)))));
            results.sort(null);
        }
        return "leaves=" + ids.size() + " owners=" + ids.values().stream().sorted().toList()
                + " run=" + execute(launcher, req) + " reruns=" + results + " ids=" + ids.keySet();
    }
}
