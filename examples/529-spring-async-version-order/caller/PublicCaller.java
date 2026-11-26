import org.springframework.web.accept.SemanticApiVersionParser;
import org.springframework.web.reactive.accept.*;
import org.springframework.web.testfixture.http.server.reactive.MockServerHttpRequest;
import org.springframework.web.testfixture.server.MockServerWebExchange;

import reactor.core.publisher.Mono;
import reactor.test.publisher.TestPublisher;

import java.util.*;
import java.util.concurrent.atomic.*;

public class PublicCaller {
    public static String observe(String[] args) {
        var gate = TestPublisher.<String>create();
        AtomicInteger subscriptions = new AtomicInteger();
        AsyncApiVersionResolver first =
                exchange -> args[0].equals("empty") ? Mono.empty() : gate.flux().next();
        AsyncApiVersionResolver second =
                exchange ->
                        Mono.defer(
                                () -> {
                                    subscriptions.incrementAndGet();
                                    return Mono.just("2.0");
                                });
        var strategy =
                new DefaultApiVersionStrategy(
                        List.of(first, second),
                        new SemanticApiVersionParser(),
                        null,
                        null,
                        false,
                        null,
                        null);
        List<String> read = new ArrayList<>();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        AtomicBoolean complete = new AtomicBoolean();
        var sentinel = new IllegalArgumentException("version fixture");
        strategy.resolveApiVersion(MockServerWebExchange.from(MockServerHttpRequest.get("/")))
                .subscribe(read::add, failure::set, () -> complete.set(true));
        if (args[0].equals("error")) gate.error(sentinel);
        else gate.emit("1.0");
        String terminal =
                complete.get() ? "complete" : failure.get() == sentinel ? "sentinel" : "other";
        return read + ":" + terminal + (args[0].equals("error") ? ":B=" + subscriptions.get() : "");
    }
}
