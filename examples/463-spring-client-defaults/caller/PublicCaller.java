import java.util.*;
import org.springframework.http.*;
import org.springframework.http.client.*;
import org.springframework.http.server.reactive.HttpHandler;
import org.springframework.mock.http.client.*;
import org.springframework.test.web.reactive.server.*;
import org.springframework.web.client.RestClient;
import org.springframework.web.reactive.function.client.WebClient;

public class PublicCaller {
    String received;

    void record(HttpHeaders headers, Map<String, List<String>> cookies) {
        received = headers.getOrEmpty("X-Mode") + "/" + cookies.getOrDefault("id", List.of())
                + "/" + headers.getOrEmpty("X-Extra") + "/" + cookies.getOrDefault("extra", List.of());
    }

    HttpHandlerConnector connector() {
        HttpHandler handler = (req, res) -> {
            Map<String, List<String>> cookies = new HashMap<>();
            req.getCookies().forEach((name, values) -> cookies.put(name, values.stream().map(HttpCookie::getValue).toList()));
            record(req.getHeaders(), cookies);
            res.setStatusCode(HttpStatus.OK);
            return res.setComplete();
        };
        return new HttpHandlerConnector(handler);
    }

    String rest(boolean freshKey) {
        ClientHttpRequestFactory transport = (uri, method) -> new MockClientHttpRequest(method, uri) {
            @Override protected ClientHttpResponse executeInternal() {
                Map<String, List<String>> values = new HashMap<>();
                for (String line : getHeaders().getOrEmpty(HttpHeaders.COOKIE)) {
                    for (String pair : line.split("; *")) {
                        String[] kv = pair.split("=", 2);
                        values.computeIfAbsent(kv[0], k -> new ArrayList<>()).add(kv[1]);
                    }
                }
                record(getHeaders(), values);
                return new MockClientHttpResponse(new byte[0], HttpStatus.OK);
            }
        };
        var base = RestClient.builder().requestFactory(transport).defaultHeaders(h -> h.add("X-Mode", "one")).defaultCookie("id","one").build();
        var edit = base.mutate().defaultHeaders(h -> h.add(freshKey ? "X-Extra" : "X-Mode", "two"))
                .defaultCookie(freshKey ? "extra" : "id", "two").build();
        edit.get().uri("http://example.invalid/").retrieve().toBodilessEntity();
        String first = received;
        base.mutate().build().get().uri("http://example.invalid/").retrieve().toBodilessEntity();
        return first + " -> " + received;
    }

    String web(boolean freshKey) {
        var base = WebClient.builder().clientConnector(connector()).defaultHeaders(h -> h.add("X-Mode", "one")).defaultCookie("id","one").build();
        var edit = base.mutate().defaultHeaders(h -> h.add(freshKey ? "X-Extra" : "X-Mode","two"))
                .defaultCookie(freshKey ? "extra" : "id","two").build();
        edit.get().uri("/").retrieve().toBodilessEntity().block();
        String first = received;
        base.mutate().build().get().uri("/").retrieve().toBodilessEntity().block();
        return first + " -> " + received;
    }

    String test(boolean freshKey, boolean snapshot) {
        var builder = WebTestClient.bindToServer(connector()).baseUrl("http://example.invalid")
                .defaultHeaders(h -> h.add("X-Mode", "one")).defaultCookie("id","one");
        var base = builder.build();
        var edit = (snapshot ? builder : base.mutate())
                .defaultHeaders(h -> h.add(freshKey ? "X-Extra" : "X-Mode","two"))
                .defaultCookie(freshKey ? "extra" : "id","two").build();
        edit.get().uri("/").exchange().expectStatus().isOk();
        String first = received;
        (snapshot ? base : base.mutate().build()).get().uri("/").exchange().expectStatus().isOk();
        return snapshot ? "B=" + first + " A=" + received : first + " -> " + received;
    }

    public static String observe(String[] args) {
        var c = new PublicCaller();
        if (args[0].equals("snapshot")) return c.test(false,true);
        boolean freshKey = args[0].equals("new");
        return "rest=" + c.rest(freshKey) + " web=" + c.web(freshKey) + " test=" + c.test(freshKey,false);
    }
}
