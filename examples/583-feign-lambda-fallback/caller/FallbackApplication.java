package app;

import com.sun.net.httpserver.HttpServer;

import feign.RequestLine;

import io.github.resilience4j.feign.*;

import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

public class FallbackApplication {
    public interface Service {
        @RequestLine("GET /greeting")
        String greeting();
    }

    static Service lambda(String text) {
        return () -> text;
    }

    public static String exercise(String mode) throws Exception {
        var gets = new AtomicInteger();
        var factories = new AtomicInteger();
        var stub = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
        stub.createContext(
                "/greeting",
                exchange -> {
                    try (exchange) {
                        if (exchange.getRequestMethod().equals("GET")) gets.incrementAndGet();
                        byte[] body = "server".getBytes(StandardCharsets.UTF_8);
                        exchange.getResponseHeaders().set("Content-Type", "text/plain");
                        exchange.sendResponseHeaders(
                                mode.equals("control") ? 200 : 400, body.length);
                        exchange.getResponseBody().write(body);
                    }
                });
        stub.start();
        try {
            var decorators =
                    FeignDecorators.builder()
                            .withFallbackFactory(
                                    e -> {
                                        int n = factories.incrementAndGet();
                                        return lambda(
                                                mode.equals("challenge")
                                                        ? "fallback-" + n
                                                        : "fallback");
                                    })
                            .build();
            Service service =
                    Resilience4jFeign.builder(decorators)
                            .target(
                                    Service.class,
                                    "http://localhost:" + stub.getAddress().getPort());
            List<String> results = new ArrayList<>();
            String output;
            try {
                results.add(service.greeting());
                if (mode.equals("challenge")) results.add(service.greeting());
                output =
                        mode.equals("challenge")
                                ? "results=" + results
                                : "result=" + results.get(0);
            } catch (Exception e) {
                Throwable root = e;
                while (root.getCause() != null) root = root.getCause();
                output = "error=" + root.getClass().getName();
            }
            return "gets=" + gets + ",factories=" + factories + "," + output;
        } finally {
            stub.stop(0);
        }
    }
}
