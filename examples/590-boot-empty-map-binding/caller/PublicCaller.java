import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.TreeMap;
import org.springframework.boot.Banner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.convert.ConversionException;

public class PublicCaller {
    @ConfigurationProperties("test")
    public static class Options {
        private Map<String, String> testmap;
        public Map<String, String> getTestmap() { return this.testmap; }
        public void setTestmap(Map<String, String> map) { this.testmap = map; }
    }
    @Configuration(proxyBeanMethods = false)
    @EnableConfigurationProperties(Options.class)
    public static class Config {}

    static String map(Map<String, String> inputs) {
        var bound = new Binder(new MapConfigurationPropertySource(inputs))
                .bind("foo", Bindable.mapOf(String.class, String.class));
        return bound.isBound() ? "bound:" + new TreeMap<>(bound.get()) : "unbound";
    }

    static String start(boolean sibling) throws Exception {
        Path yaml = Files.createTempFile("empty-map-", ".yaml");
        Files.writeString(yaml, sibling ? "test: {testmap: {}, label: kept}\n" : "test: {testmap: {}}\n");
        SpringApplication app = new SpringApplication(Config.class);
        app.setWebApplicationType(WebApplicationType.NONE);
        app.setBannerMode(Banner.Mode.OFF);
        try (var context = app.run("--spring.config.location=" + yaml.toUri())) {
            Map<String, String> map = context.getBean(Options.class).getTestmap();
            return map == null ? "absent" : new TreeMap<>(map).toString();
        } catch (RuntimeException error) {
            return conversionFailure(error);
        } finally {
            Files.deleteIfExists(yaml);
        }
    }

    static String conversionFailure(RuntimeException failure) {
        for (Throwable t = failure; t != null; t = t.getCause()) {
            if (t instanceof ConversionException) return "conversion-failed";
        }
        throw failure;
    }

    public static String observe(String[] args) throws Exception {
        try {
            return switch (args[0]) {
                case "intent" -> map(Map.of("foo", ""));
                case "control" -> map(Map.of("foo.a", "one", "foo.b", "two"));
                case "challenge" -> start(false) + "/" + start(true);
                default -> throw new IllegalArgumentException(args[0]);
            };
        } catch (RuntimeException failure) {
            return conversionFailure(failure);
        }
    }
}
