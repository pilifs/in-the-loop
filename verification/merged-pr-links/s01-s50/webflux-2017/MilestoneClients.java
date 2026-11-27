package fixture.webflux;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import com.sun.net.httpserver.HttpServer;
import org.springframework.boot.test.autoconfigure.web.reactive.WebTestClientAutoConfiguration;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
@Import({PersonApplication.class,WebTestClientAutoConfiguration.class})
public class MilestoneClients {
    public static String read(ConfigurableApplicationContext context) throws Exception {
        HttpServer source = HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        byte[] fixed = "{\"first_name\":\"Mia\"}".getBytes(StandardCharsets.UTF_8);
        source.createContext("/fixed", exchange -> {
            exchange.getResponseHeaders().add("Content-Type","application/json");
            exchange.sendResponseHeaders(200,fixed.length);
            try (java.io.OutputStream out = exchange.getResponseBody()) { out.write(fixed); }
        });
        source.start();
        try {
            String uri = "http://127.0.0.1:" + source.getAddress().getPort() + "/fixed";
            PersonApplication.Person client = context.getBean(WebClient.Builder.class).build().get().uri(uri).exchange()
                    .flatMap(response -> response.bodyToMono(PersonApplication.Person.class)).block();
            PersonApplication.Person test = context.getBean(WebTestClient.class).get().uri("/fixed").exchange()
                    .expectStatus().isOk().expectBody(PersonApplication.Person.class).returnResult().getResponseBody();
            return client.getFirstName() + "/" + test.getFirstName();
        } finally { source.stop(0); }
    }
}
