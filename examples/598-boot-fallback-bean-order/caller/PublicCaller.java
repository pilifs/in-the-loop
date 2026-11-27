import java.util.concurrent.atomic.AtomicReference;
import org.springframework.boot.autoconfigure.AutoConfigureBefore;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

public class PublicCaller {
    record Choice(String marker) {}
    record BridgeMarker(String marker) {}
    @Configuration(proxyBeanMethods = false)
    static class Fallback {
        @Bean @ConditionalOnMissingBean(Choice.class) Choice fallback() { return new Choice("fallback"); }
    }
    @Configuration(proxyBeanMethods = false) @AutoConfigureBefore(Fallback.class)
    static class Preferred {
        @Bean @ConditionalOnMissingBean(Choice.class) Choice preferred() { return new Choice("preferred"); }
    }
    @Configuration(proxyBeanMethods = false) @AutoConfigureBefore(Fallback.class)
    static class Bridge {
        @Bean BridgeMarker bridge() { return new BridgeMarker("bridge"); }
    }
    @Configuration(proxyBeanMethods = false) @AutoConfigureBefore(Bridge.class)
    static class Indirect {
        @Bean @ConditionalOnMissingBean(Choice.class) Choice preferred() { return new Choice("preferred"); }
    }
    static String run(Class<?>... configurations) {
        var answer = new AtomicReference<String>();
        new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(configurations)).run(ctx -> {
            var choices = ctx.getBeansOfType(Choice.class);
            String markers = String.join(",", choices.values().stream().map(Choice::marker).sorted().toList());
            var bridge = ctx.getBeanProvider(BridgeMarker.class).getIfAvailable();
            answer.set(choices.size() + ":" + markers + (bridge == null ? "" : ":" + bridge.marker()));
        });
        return answer.get();
    }
    public static String observe(String[] args) {
        return switch (args[0]) {
            case "intent" -> run(Fallback.class, Preferred.class);
            case "control" -> run(Fallback.class);
            case "challenge" -> run(Fallback.class, Bridge.class, Indirect.class) + "/" + run(Indirect.class, Bridge.class, Fallback.class);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
