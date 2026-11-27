import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.convert.ConversionException;
import org.springframework.core.env.MapPropertySource;

public class PublicCaller {
    @ConfigurationProperties("test")
    public record Options(@DefaultValue("${defaults.duration:1d}") Duration duration) {}

    @Configuration(proxyBeanMethods = false)
    @EnableConfigurationProperties(Options.class)
    public static class Config {}

    static String bind(String fallback, boolean explicit) {
        Map<String, Object> inputs = new HashMap<>();
        inputs.put("defaults.duration", fallback);
        if (explicit) inputs.put("test.duration", "5d");
        try (var context = new AnnotationConfigApplicationContext()) {
            context.getEnvironment().getPropertySources().addFirst(new MapPropertySource("fixture", inputs));
            context.register(Config.class);
            context.refresh();
            return context.getBean(Options.class).duration().toString();
        } catch (RuntimeException failure) {
            for (Throwable t = failure; t != null; t = t.getCause()) {
                if (t instanceof ConversionException) return "conversion-failed";
            }
            throw failure;
        }
    }

    public static String observe(String[] args) {
        return switch (args[0]) {
            case "intent" -> bind("3d", false);
            case "control" -> bind("3d", true);
            case "challenge" -> bind("not-a-duration", true) + "/" + bind("not-a-duration", false);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
