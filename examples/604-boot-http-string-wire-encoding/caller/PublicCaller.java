import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.HexFormat;
import java.util.concurrent.atomic.AtomicReference;
import org.apache.catalina.startup.Tomcat;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.http.converter.autoconfigure.*;
import org.springframework.boot.autoconfigure.ImportAutoConfiguration;
import org.springframework.context.annotation.*;
import org.springframework.http.MediaType;
import org.springframework.http.converter.*;
import org.springframework.http.converter.HttpMessageConverters;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClient;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.servlet.DispatcherServlet;
import org.springframework.web.servlet.config.annotation.*;

public class PublicCaller {
    static final AtomicReference<byte[]> received = new AtomicReference<>();
    @RestController static class Page {
        @GetMapping(value="/value", produces="text/plain") public String value() { return "é"; }
        @PostMapping("/receive") public void take(jakarta.servlet.http.HttpServletRequest req) throws Exception {
            received.set(req.getInputStream().readAllBytes());
        }
    }
    @Configuration(proxyBeanMethods=false) @EnableWebMvc @ImportAutoConfiguration(HttpMessageConvertersAutoConfiguration.class)
    static class Config implements WebMvcConfigurer {
        private final ObjectProvider<ServerHttpMessageConvertersCustomizer> server;
        Config(ObjectProvider<ServerHttpMessageConvertersCustomizer> server) { this.server = server; }
        @Bean Page page() { return new Page(); }
        @Override public void configureMessageConverters(HttpMessageConverters.ServerBuilder builder) {
            server.orderedStream().forEach(c -> c.customize(builder));
        }
    }
    @Configuration(proxyBeanMethods=false)
    static class Custom {
        @Bean ServerHttpMessageConvertersCustomizer serverStrings() {
            return builder -> builder.withStringConverter(new StringHttpMessageConverter(StandardCharsets.ISO_8859_1));
        }
        @Bean ClientHttpMessageConvertersCustomizer clientStrings() {
            return builder -> builder.withStringConverter(new StringHttpMessageConverter(StandardCharsets.ISO_8859_1));
        }
    }
    public static String observe(String[] args) throws Exception {
        var server = new Tomcat();
        var home = Files.createTempDirectory("charset-tomcat").toFile();
        server.setBaseDir(home.toString());
        server.setPort(0);
        var connector = server.getConnector();
        connector.setProperty("address", "127.0.0.1");
        var servlet = server.addContext("", home.toString());
        var app = new AnnotationConfigWebApplicationContext();
        app.register(Config.class);
        if (!args[0].equals("control")) app.register(Custom.class);
        var wrapper = Tomcat.addServlet(servlet, "dispatcher", new DispatcherServlet(app));
        wrapper.setLoadOnStartup(1);
        servlet.addServletMappingDecoded("/", "dispatcher");
        try {
            server.start();
            String host = "http://127.0.0.1:" + connector.getLocalPort();
            var wire = HttpClient.newHttpClient().send(HttpRequest.newBuilder(URI.create(host + "/value"))
                    .header("Accept", "text/plain").GET().build(), HttpResponse.BodyHandlers.ofByteArray());
            String result = wire.statusCode() + ":" + HexFormat.of().formatHex(wire.body());
            if (!args[0].equals("challenge")) return result;
            var client = RestClient.builder().configureMessageConverters(builder -> app
                    .getBeanProvider(ClientHttpMessageConvertersCustomizer.class).orderedStream().forEach(c -> c.customize(builder))).build();
            var response = client.post().uri(host + "/receive").contentType(MediaType.TEXT_PLAIN).body("é").retrieve().toBodilessEntity();
            return result + "/" + response.getStatusCode().value() + ":" + HexFormat.of().formatHex(received.get());
        } finally { server.stop(); server.destroy(); }
    }
}
