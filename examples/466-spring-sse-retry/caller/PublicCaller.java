import java.util.*;
import reactor.core.publisher.Mono;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.*;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.reactive.function.client.*;

public class PublicCaller {
    static String read(String text) {
        var client = WebClient.builder().exchangeFunction(request -> Mono.just(ClientResponse.create(HttpStatus.OK)
                .header(HttpHeaders.CONTENT_TYPE, MediaType.TEXT_EVENT_STREAM_VALUE).body(text).build())).build();
        var events = client.get().uri("/events").retrieve().bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {});
        var values = new ArrayList<String>();
        try {
            events.doOnNext(e -> values.add(e.data() + "@" + (e.retry() == null ? null : e.retry().toMillis()))).blockLast();
            return values + " complete";
        } catch (RuntimeException e) {
            Throwable root = e;
            while (root.getCause() != null) root = root.getCause();
            return values + " error=" + e.getClass().getSimpleName() + " cause=" + root.getClass().getSimpleName();
        }
    }

    public static String observe(String[] args) {
        return switch (args[0]) {
            case "bad" -> read("retry:none\ndata:foo\n\ndata:bar\n\n");
            case "valid" -> read("retry: 25\ndata:foo\n\ndata:bar\n\n");
            case "space" -> read("retry: 25\ndata:foo\n\n") + " / " + read("retry:25 \ndata:foo\n\n");
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
