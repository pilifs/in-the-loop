import com.fasterxml.jackson.databind.*;

import org.springframework.core.ResolvableType;
import org.springframework.core.io.buffer.*;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEventHttpMessageWriter;
import org.springframework.http.codec.json.Jackson2JsonEncoder;
import org.springframework.mock.http.server.reactive.test.MockServerHttpResponse;

import reactor.core.publisher.Flux;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class PublicCaller {
    public static class Bean {
        public String foo;
        public Object bar;

        Bean(String foo, Object bar) {
            this.foo = foo;
            this.bar = bar;
        }
    }

    static List<String> events(String wire) {
        List<String> received = new ArrayList<>(), fields = new ArrayList<>();
        for (String line : wire.split("\n", -1)) {
            if (line.isEmpty() && !fields.isEmpty()) {
                received.add(String.join("\n", fields));
                fields.clear();
            } else if (line.startsWith("data:")) {
                String field = line.substring(5);
                fields.add(field.startsWith(" ") ? field.substring(1) : field);
            }
        }
        return received;
    }

    public static String observe(String[] args) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        if (!args[0].equals("compact")) mapper.enable(SerializationFeature.INDENT_OUTPUT);
        boolean nested = args[0].equals("nested");
        ServerSentEventHttpMessageWriter writer =
                new ServerSentEventHttpMessageWriter(
                        Collections.singletonList(new Jackson2JsonEncoder(mapper)));
        MockServerHttpResponse response = new MockServerHttpResponse();
        Flux<Bean> beans =
                Flux.just(
                        new Bean(nested ? "A\nB" : "A", "one"),
                        new Bean(
                                "B", nested ? Collections.singletonMap("value", "nested") : "two"));
        writer.write(
                        beans,
                        ResolvableType.forClass(Bean.class),
                        MediaType.TEXT_EVENT_STREAM,
                        response,
                        Collections.emptyMap())
                .blockMillis(5000);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        Flux.from(response.getBodyWithFlush())
                .concatMap(group -> Flux.from(group))
                .doOnNext(
                        buffer -> {
                            byte[] part = new byte[buffer.readableByteCount()];
                            buffer.read(part);
                            bytes.write(part, 0, part.length);
                            DataBufferUtils.release(buffer);
                        })
                .then()
                .blockMillis(5000);
        List<String> payloads = events(new String(bytes.toByteArray(), StandardCharsets.UTF_8)),
                read = new ArrayList<>();
        for (String data : payloads) {
            try (com.fasterxml.jackson.core.JsonParser parser =
                    mapper.getFactory().createParser(data)) {
                JsonNode value = mapper.readTree(parser);
                if (parser.nextToken() != null) throw new IllegalStateException("extra JSON");
                JsonNode bar = value.path("bar");
                read.add(
                        value.path("foo").asText().replace("\n", "<LF>")
                                + "/"
                                + (bar.isObject() ? bar.path("value") : bar).asText());
            } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
                read.add("invalid");
            }
        }
        return "events=" + payloads.size() + ":" + String.join(",", read);
    }
}
