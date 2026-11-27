import java.io.IOException;
import java.net.URI;
import java.net.http.*;
import java.util.*;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.jsontype.TypeSerializer;
import com.fasterxml.jackson.databind.module.SimpleModule;
import org.glassfish.jersey.server.ResourceConfig;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.ImportAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.beans.BeansEndpointAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.endpoint.EndpointAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.endpoint.web.WebEndpointAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.web.server.ManagementContextAutoConfiguration;
import org.springframework.boot.actuate.endpoint.jackson.EndpointJackson2ObjectMapper;
import org.springframework.boot.jackson2.autoconfigure.Jackson2AutoConfiguration;
import org.springframework.boot.jersey.autoconfigure.JerseyAutoConfiguration;
import org.springframework.boot.servlet.autoconfigure.actuate.web.ServletManagementContextAutoConfiguration;
import org.springframework.boot.tomcat.autoconfigure.actuate.web.server.TomcatServletManagementContextAutoConfiguration;
import org.springframework.boot.tomcat.autoconfigure.servlet.TomcatServletWebServerAutoConfiguration;
import org.springframework.context.annotation.*;

public class PublicCaller {
    @Configuration(proxyBeanMethods=false)
    @ImportAutoConfiguration({Jackson2AutoConfiguration.class, JerseyAutoConfiguration.class, EndpointAutoConfiguration.class,
            TomcatServletWebServerAutoConfiguration.class, WebEndpointAutoConfiguration.class,
            ManagementContextAutoConfiguration.class, BeansEndpointAutoConfiguration.class,
            ServletManagementContextAutoConfiguration.class,TomcatServletManagementContextAutoConfiguration.class})
    static class App {
        @Bean ResourceConfig resourceConfig() { return new ResourceConfig(); }
        @Bean Object fixtureSingleton() { return new Object(); }
        @Bean @Scope("prototype") Object fixturePrototype() { return new Object(); }
        @Bean EndpointJackson2ObjectMapper endpointMapper() {
            var module = new SimpleModule();
            module.addSerializer(String.class, new JsonSerializer<String>() {
                public void serialize(String value, JsonGenerator gen, SerializerProvider sp) throws IOException {
                    gen.writeString(new StringBuilder(value).reverse().toString());
                }
                public void serializeWithType(String v,JsonGenerator g,SerializerProvider sp,TypeSerializer t) throws IOException {
                    serialize(v,g,sp);
                }
            });
            var mapper = new ObjectMapper().registerModule(module);
            return () -> mapper;
        }
    }
    public static String observe(String[] args) throws Exception {
        boolean separate = !args[0].equals("control");
        var app = new SpringApplication(App.class);
        app.setWebApplicationType(WebApplicationType.SERVLET);
        var settings = new ArrayList<>(List.of("--server.port=0","--server.address=127.0.0.1","--management.endpoints.web.exposure.include=beans"));
        if (separate) settings.addAll(List.of("--management.server.port=0","--management.server.address=127.0.0.1"));
        try (var ctx = app.run(settings.toArray(String[]::new)); var client = HttpClient.newHttpClient()) {
            String port = ctx.getEnvironment().getRequiredProperty(separate ? "local.management.port" : "local.server.port");
            var res = client.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/actuator/beans"))
                    .header("Accept","application/json").GET().build(),HttpResponse.BodyHandlers.ofByteArray());
            if (res.statusCode() != 200) return String.valueOf(res.statusCode());
            var contexts = new ObjectMapper().readTree(res.body()).path("contexts");
            for (var context : contexts) {
                var beans = context.path("beans");
                if (!beans.has("fixtureSingleton")) continue;
                String first = beans.path("fixtureSingleton").path("scope").asText();
                return "200:" + first + (args[0].equals("challenge") ? ":" + beans.path("fixturePrototype").path("scope").asText() : "");
            }
            return "missing-fixture";
        }
    }
}
