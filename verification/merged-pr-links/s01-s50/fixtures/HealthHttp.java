import java.net.URI;
import java.net.http.*;
import java.util.*;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.ImportAutoConfiguration;
import org.springframework.boot.autoconfigure.availability.ApplicationAvailabilityAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.endpoint.EndpointAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.endpoint.web.WebEndpointAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.web.server.ManagementContextAutoConfiguration;
import org.springframework.boot.health.autoconfigure.actuate.endpoint.*;
import org.springframework.boot.health.autoconfigure.application.*;
import org.springframework.boot.health.autoconfigure.contributor.HealthContributorAutoConfiguration;
import org.springframework.boot.health.autoconfigure.registry.HealthContributorRegistryAutoConfiguration;
import org.springframework.boot.http.converter.autoconfigure.HttpMessageConvertersAutoConfiguration;
import org.springframework.boot.jackson.autoconfigure.JacksonAutoConfiguration;
import org.springframework.boot.servlet.autoconfigure.actuate.web.ServletManagementContextAutoConfiguration;
import org.springframework.boot.tomcat.autoconfigure.actuate.web.server.TomcatServletManagementContextAutoConfiguration;
import org.springframework.boot.tomcat.autoconfigure.servlet.TomcatServletWebServerAutoConfiguration;
import org.springframework.boot.webmvc.autoconfigure.*;
import org.springframework.boot.webmvc.autoconfigure.actuate.endpoint.web.WebMvcHealthEndpointExtensionAutoConfiguration;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.ConfigurableApplicationContext;
import tools.jackson.databind.json.JsonMapper;

/** Reads the status and exposed component names over the actual local MVC transport. */
public class HealthHttp implements AutoCloseable {
    @Configuration(proxyBeanMethods=false)
    @ImportAutoConfiguration({JacksonAutoConfiguration.class, HealthContributorAutoConfiguration.class,
            HealthContributorRegistryAutoConfiguration.class, HttpMessageConvertersAutoConfiguration.class,
            ManagementContextAutoConfiguration.class, TomcatServletWebServerAutoConfiguration.class,
            TomcatServletManagementContextAutoConfiguration.class, WebMvcAutoConfiguration.class,
            ServletManagementContextAutoConfiguration.class, WebEndpointAutoConfiguration.class,
            EndpointAutoConfiguration.class, DispatcherServletAutoConfiguration.class, HealthEndpointAutoConfiguration.class,
            WebMvcHealthEndpointExtensionAutoConfiguration.class, DiskSpaceHealthContributorAutoConfiguration.class,
            ApplicationAvailabilityAutoConfiguration.class, AvailabilityHealthContributorAutoConfiguration.class,
            AvailabilityProbesAutoConfiguration.class})
    public static class Transport {}

    private final ConfigurableApplicationContext context;
    private final HttpClient client = HttpClient.newHttpClient();
    HealthHttp(Class<?> contributors, String... settings) {
        var app = new SpringApplication(Transport.class, contributors);
        app.setWebApplicationType(WebApplicationType.SERVLET);
        var args = new ArrayList<>(List.of("--server.address=127.0.0.1", "--server.port=0",
                "--management.endpoints.web.exposure.include=health"));
        for (String s : settings) args.add("--" + s);
        context = app.run(args.toArray(String[]::new));
    }
    String get(String path, boolean names) throws Exception {
        URI uri = URI.create("http://127.0.0.1:" + context.getEnvironment().getRequiredProperty("local.server.port") + path);
        var response = client.send(HttpRequest.newBuilder(uri).header("Accept","application/json").GET().build(),
                HttpResponse.BodyHandlers.ofByteArray());
        if (response.statusCode() != 200 && response.statusCode() != 503) return String.valueOf(response.statusCode());
        var json = new JsonMapper().readTree(response.body());
        String status = response.statusCode() + ":" + json.path("status").asString();
        if (!names) return status;
        var components = new TreeSet<String>();
        json.path("components").propertyNames().forEach(components::add);
        return status + ":" + String.join(",",components);
    }
    public void close() { try { context.close(); } finally { client.close(); } }
}
