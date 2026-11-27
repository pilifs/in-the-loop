import java.net.URI;
import java.net.http.*;
import java.util.Map;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.glassfish.jersey.server.ResourceConfig;
import org.springframework.boot.*;
import org.springframework.boot.autoconfigure.ImportAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.endpoint.EndpointAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.endpoint.web.WebEndpointAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.web.server.ManagementContextAutoConfiguration;
import org.springframework.boot.health.autoconfigure.actuate.endpoint.HealthEndpointAutoConfiguration;
import org.springframework.boot.health.autoconfigure.contributor.HealthContributorAutoConfiguration;
import org.springframework.boot.health.autoconfigure.registry.HealthContributorRegistryAutoConfiguration;
import org.springframework.boot.health.contributor.*;
import org.springframework.boot.jackson2.autoconfigure.Jackson2AutoConfiguration;
import org.springframework.boot.jersey.autoconfigure.JerseyAutoConfiguration;
import org.springframework.boot.jersey.autoconfigure.actuate.endpoint.web.HealthEndpointJerseyExtensionAutoConfiguration;
import org.springframework.boot.servlet.autoconfigure.actuate.web.ServletManagementContextAutoConfiguration;
import org.springframework.boot.tomcat.autoconfigure.actuate.web.server.TomcatServletManagementContextAutoConfiguration;
import org.springframework.boot.tomcat.autoconfigure.servlet.TomcatServletWebServerAutoConfiguration;
import org.springframework.context.annotation.*;

public class PublicCaller {
    @Configuration(proxyBeanMethods=false)
    @ImportAutoConfiguration({Jackson2AutoConfiguration.class, JerseyAutoConfiguration.class, EndpointAutoConfiguration.class,
            TomcatServletWebServerAutoConfiguration.class, WebEndpointAutoConfiguration.class, ManagementContextAutoConfiguration.class,
            ServletManagementContextAutoConfiguration.class,TomcatServletManagementContextAutoConfiguration.class,
            HealthContributorAutoConfiguration.class,HealthContributorRegistryAutoConfiguration.class,
            HealthEndpointAutoConfiguration.class,HealthEndpointJerseyExtensionAutoConfiguration.class})
    static class App {
        @Bean ResourceConfig resources() { return new ResourceConfig(); }
        @Bean CompositeHealthContributor test() {
            return CompositeHealthContributor.fromMap(Map.of("spring", (HealthIndicator) () -> Health.up().build()));
        }
    }
    static String get(HttpClient client, String base, String leaf) throws Exception {
        var res = client.send(HttpRequest.newBuilder(URI.create(base + leaf)).header("Accept","application/json")
                .GET().build(),HttpResponse.BodyHandlers.ofByteArray());
        if (res.statusCode() != 200) return String.valueOf(res.statusCode());
        return "200:" + new ObjectMapper().readTree(res.body()).path("status").asText();
    }
    public static String observe(String[] args) throws Exception {
        if (!args[0].equals("control")) throw new IllegalArgumentException(args[0]);
        var app = new SpringApplication(App.class);
        app.setWebApplicationType(WebApplicationType.SERVLET);
        try (var ctx = app.run("--server.address=127.0.0.1","--server.port=0","--management.endpoints.web.exposure.include=health",
                "--management.endpoint.health.show-components=always"); var client = HttpClient.newHttpClient()) {
            String base = "http://127.0.0.1:" + ctx.getEnvironment().getRequiredProperty("local.server.port") + "/actuator/health/test/";
            return get(client,base,"spring") + "/" + get(client,base,"missing");
        }
    }
}
