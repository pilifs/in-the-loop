import java.util.Map;
import io.micrometer.core.instrument.Metrics;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.core.env.MapPropertySource;
import org.springframework.boot.micrometer.metrics.autoconfigure.MetricsAutoConfiguration;

public class PublicCaller {
    static AnnotationConfigApplicationContext context(boolean useGlobal) {
        var ctx = new AnnotationConfigApplicationContext();
        ctx.getEnvironment().getPropertySources().addFirst(new MapPropertySource("fixture",
                Map.of("management.metrics.use-global-registry", String.valueOf(useGlobal))));
        ctx.register(MetricsAutoConfiguration.class);
        ctx.refresh();
        return ctx;
    }
    static SimpleMeterRegistry late(AnnotationConfigApplicationContext ctx, String name) {
        ctx.registerBean(name, SimpleMeterRegistry.class, SimpleMeterRegistry::new);
        return ctx.getBean(name, SimpleMeterRegistry.class);
    }
    static boolean member(SimpleMeterRegistry registry) {
        return Metrics.globalRegistry.getRegistries().stream().anyMatch(candidate -> candidate == registry);
    }
    static String state(SimpleMeterRegistry registry) { return member(registry) + ":" + registry.isClosed(); }
    public static String observe(String[] args) {
        boolean control = args[0].equals("control");
        try (var a = context(!control)) {
            var first = late(a, "first");
            boolean before = member(first);
            if (control) {
                first.counter("local.calls").increment();
                double value = first.counter("local.calls").count();
                a.close();
                return before + ":" + value + ":" + member(first);
            }
            if (args[0].equals("intent")) {
                a.close();
                return before + "/" + state(first);
            }
            try (var b = context(true)) {
                var second = late(b, "second");
                if (!before || !member(second)) throw new AssertionError("late registries did not join");
                a.close();
                second.counter("survivor.calls").increment();
                String after = state(first) + "/" + state(second) + ":" + second.counter("survivor.calls").count();
                b.close();
                return after + "/" + state(second);
            }
        }
    }
}
