import org.springframework.web.server.adapter.WebHttpHandlerBuilder;
import org.springframework.web.testfixture.http.server.reactive.*;

import reactor.core.publisher.Mono;

import java.util.*;

public class PublicCaller {
    static void add(WebHttpHandlerBuilder builder, String marker) {
        builder.httpHandlerDecorator(
                next ->
                        (req, res) ->
                                next.handle(
                                        req.mutate()
                                                .headers(headers -> headers.add("X-Step", marker))
                                                .build(),
                                        res));
    }

    static String send(WebHttpHandlerBuilder builder, List<String> records) {
        records.clear();
        builder.build()
                .handle(MockServerHttpRequest.get("/probe").build(), new MockServerHttpResponse())
                .block();
        return String.join(",", records);
    }

    public static String observe(String[] args) {
        List<String> records = new ArrayList<>();
        var root =
                WebHttpHandlerBuilder.webHandler(
                        exchange -> {
                            var req = exchange.getRequest();
                            records.add(
                                    req.getPath()
                                            + ":"
                                            + req.getHeaders().getOrDefault("X-Step", List.of()));
                            return Mono.empty();
                        });
        if (!args[0].equals("empty")) add(root, "A");
        var clone = root.clone();
        if (args[0].equals("extend")) {
            add(clone, "B");
            add(root, "C");
            return send(clone, records)
                    + " / "
                    + send(root, records)
                    + " / "
                    + send(root.clone(), records);
        }
        return send(root, records) + " / " + send(clone, records);
    }
}
