import java.nio.file.Files;
import java.nio.file.Path;
import org.springframework.boot.Banner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.context.config.ConfigDataResourceNotFoundException;
import org.springframework.context.annotation.Configuration;

public class PublicCaller {
    @Configuration(proxyBeanMethods = false) public static class Config {}

    static String start(boolean hint, boolean neighbor) throws Exception {
        Path root = Files.createTempDirectory("spring-config");
        Path plain = Files.createDirectory(root.resolve("team"));
        Path bracket = Files.createDirectory(root.resolve("team[a]"));
        Files.writeString(bracket.resolve("app.properties"), "marker=selected\n");
        Files.writeString(plain.resolve("app"), "marker=hinted\n");
        if (neighbor) Files.writeString(plain.resolve("app.properties"), "marker=decoy\n");
        String location = "file:" + (hint ? plain.resolve("app") + "[.properties]" : bracket.resolve("app.properties"));
        var app = new SpringApplication(Config.class);
        app.setBannerMode(Banner.Mode.OFF);
        app.setWebApplicationType(WebApplicationType.NONE);
        try (var ctx = app.run("--spring.config.import=" + location)) {
            return ctx.getEnvironment().getProperty("marker", "absent");
        } catch (ConfigDataResourceNotFoundException missing) {
            return "missing";
        }
    }

    public static String observe(String[] args) throws Exception {
        return switch (args[0]) {
            case "intent" -> start(false, false);
            case "control" -> start(true, false);
            case "challenge" -> start(false, false) + "/" + start(false, true);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
