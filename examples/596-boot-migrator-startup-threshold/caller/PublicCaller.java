import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.springframework.boot.Banner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.context.annotation.Configuration;

public class PublicCaller {
    @Configuration(proxyBeanMethods = false) static class Config {}
    static final String BANNER = "--spring.banner.image.width=10";
    static final String LOGGING = "--logging.file=test.log";
    static final String ERROR = "--spring.properties.migrator.fail=on-error";
    static final String WARN = "--spring.properties.migrator.fail=on-warning";

    static String run(String... arguments) {
        var bytes = new ByteArrayOutputStream();
        PrintStream out = System.out, err = System.err;
        String state;
        try (var stream = new PrintStream(bytes, true, StandardCharsets.UTF_8)) {
            System.setOut(stream);
            System.setErr(stream);
            var app = new SpringApplication(Config.class);
            app.setBannerMode(Banner.Mode.OFF);
            app.setWebApplicationType(WebApplicationType.NONE);
            try (var context = app.run(arguments)) {
                state = context.isActive() ? "active" : "inactive";
            } catch (IllegalStateException failure) {
                if (!"Found configuration keys that need to be migrated".equals(failure.getMessage())) throw failure;
                state = "migration-failed";
            }
        } finally {
            System.setOut(out);
            System.setErr(err);
        }
        var keys = bytes.toString(StandardCharsets.UTF_8).lines().map(String::strip).toList();
        var found = new java.util.ArrayList<String>();
        if (keys.contains("Key: spring.banner.image.width")) found.add("banner");
        if (keys.contains("Key: logging.file")) found.add("logging");
        return state + ":" + String.join("+", found);
    }
    public static String observe(String[] args) {
        return switch (args[0]) {
            case "intent" -> run(ERROR, BANNER);
            case "control" -> run(ERROR, LOGGING) + "/" + run(LOGGING) + "/" + run(WARN, LOGGING);
            case "challenge" -> run(ERROR, BANNER, LOGGING) + "/" + run(ERROR, LOGGING, BANNER);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
