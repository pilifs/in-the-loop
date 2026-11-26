import java.util.List;
import java.util.concurrent.atomic.AtomicReference;
import org.springframework.http.HttpCookie;
import org.springframework.http.HttpStatus;
import org.springframework.test.web.reactive.server.HttpHandlerConnector;
import org.springframework.test.web.reactive.server.WebTestClient;

public class PublicCaller {
    static String send(WebTestClient client, AtomicReference<String> received) {
        received.set(null);
        client.get().uri("/").exchange().expectStatus().isOk();
        return received.get();
    }

    public static String observe(String[] args) {
        var received = new AtomicReference<String>();
        var connector = new HttpHandlerConnector((request, response) -> {
            var cookies = request.getCookies().getOrDefault("id", List.of()).stream().map(HttpCookie::getValue).toList();
            received.set(request.getHeaders().getOrEmpty("X-Mode") + "/" + cookies);
            response.setStatusCode(HttpStatus.OK);
            return response.setComplete();
        });
        var original = WebTestClient.bindToServer(connector).baseUrl("http://example.invalid").defaultCookie("id","one");
        if (args[0].equals("retained-consumer")) original.defaultHeaders(h -> h.add("X-Mode","one"));
        else original.defaultHeader("X-Mode","one");
        var a = original.build();
        boolean derive = args[0].equals("derived-convenience");
        var builder = derive ? a.mutate() : original;
        try { builder.defaultHeaders(h -> h.add("X-Mode","two")); }
        catch (UnsupportedOperationException e) {
            return "append=" + e.getClass().getSimpleName() + " A=" + send(a, received);
        }
        var b = builder.defaultCookie("id","two").build();
        return "B=" + send(b, received) + " A=" + send(derive ? a.mutate().build() : a, received);
    }
}
