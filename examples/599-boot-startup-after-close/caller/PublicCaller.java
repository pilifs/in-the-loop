import java.util.ArrayList;
import java.util.List;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.Banner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.boot.context.event.ApplicationStartedEvent;
import org.springframework.context.ApplicationListener;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Lazy;

public class PublicCaller {
    static final List<String> events = new ArrayList<>();
    static boolean closeCompleted;
    static int creationsAfterClose;
    public static class Dependency implements AutoCloseable {
        Dependency() { if (closeCompleted) creationsAfterClose++; }
        public void close() {}
    }
    @Configuration(proxyBeanMethods = false)
    static class Config {
        @Bean @Lazy Dependency dependency() { return new Dependency(); }
        @Bean @Lazy ApplicationRunner runner(Dependency dependency) { return ignored -> events.add("runner"); }
    }
    static void finish(ConfigurableApplicationContext ctx) {
        ctx.close();
        closeCompleted = true;
    }
    public static String observe(String[] args) {
        String mode = args[0];
        SpringApplication app = new SpringApplication(Config.class) {
            @Override protected void afterRefresh(ConfigurableApplicationContext ctx, ApplicationArguments arguments) {
                if (mode.equals("intent")) finish(ctx);
            }
        };
        app.setBannerMode(Banner.Mode.OFF);
        app.setWebApplicationType(WebApplicationType.NONE);
        app.addListeners((ApplicationListener<ApplicationStartedEvent>) event -> {
            events.add("started");
            if (mode.equals("challenge")) finish(event.getApplicationContext());
        }, (ApplicationListener<ApplicationReadyEvent>) event -> events.add("ready"));
        try (var ctx = app.run()) {
            return (ctx.isActive() ? "active" : "inactive") + ":" + events + ":" + creationsAfterClose;
        }
    }
}
