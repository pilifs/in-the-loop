import org.springframework.boot.health.contributor.Health;
import org.springframework.boot.health.contributor.HealthIndicator;
import org.springframework.context.annotation.*;

public class PublicCaller {
    static volatile boolean healthy;
    @Configuration(proxyBeanMethods=false) static class Indicators {
        @Bean HealthIndicator sentinel() { return () -> healthy ? Health.up().build() : Health.down().build(); }
    }
    static String read(HealthHttp app) throws Exception {
        return app.get("/actuator/health/liveness",false) + "/" + app.get("/alive",false) + "/" + app.get("/actuator/health",false);
    }
    public static String observe(String[] args) throws Exception {
        var settings = new java.util.ArrayList<>(java.util.List.of("management.endpoint.health.probes.enabled=true",
                "management.endpoint.health.group.liveness.additional-path=server:/alive"));
        if (args[0].equals("control")) settings.add("management.endpoint.health.group.liveness.include=livenessState,sentinel");
        healthy = false;
        try (var app = new HealthHttp(Indicators.class,settings.toArray(String[]::new))) {
            String down = read(app);
            if (!args[0].equals("challenge")) return down;
            healthy = true;
            return down + ";" + read(app);
        }
    }
}
