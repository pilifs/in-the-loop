import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.asyncDispatch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import org.springframework.http.MediaType;
import org.springframework.http.converter.StringHttpMessageConverter;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public class ServletEvents {
    public static class Event {
        public String foo;
        public String bar;

        Event(String foo, String bar) {
            this.foo = foo;
            this.bar = bar;
        }
    }

    @RestController
    public static class Events {
        @RequestMapping(value = "/events", produces = "text/event-stream")
        public SseEmitter events() throws Exception {
            SseEmitter emitter = new SseEmitter();
            emitter.send(new Event("A", "one"), MediaType.APPLICATION_JSON);
            emitter.send(new Event("B", "two"), MediaType.APPLICATION_JSON);
            emitter.complete();
            return emitter;
        }
    }

    public static String observe(String[] args) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        if (args[0].equals("pretty")) mapper.enable(SerializationFeature.INDENT_OUTPUT);
        MockMvc mvc =
                MockMvcBuilders.standaloneSetup(new Events())
                        .setMessageConverters(
                                new StringHttpMessageConverter(StandardCharsets.UTF_8),
                                new MappingJackson2HttpMessageConverter(mapper))
                        .build();
        MvcResult first = mvc.perform(get("/events").accept("text/event-stream")).andReturn();
        if (first.getRequest().isAsyncStarted()) {
            mvc.perform(asyncDispatch(first));
        }
        // The emitter writes on the original servlet response, before async dispatch.
        if (!first.getResponse().getContentType().startsWith("text/event-stream")) {
            throw new IllegalStateException("emitter did not produce an event stream");
        }
        List<String> lines = new ArrayList<>(), values = new ArrayList<>();
        String wire =
                new String(first.getResponse().getContentAsByteArray(), StandardCharsets.UTF_8);
        for (String line : wire.split("\\r?\\n", -1)) {
            if (line.startsWith("data:")) {
                String field = line.substring(5);
                lines.add(field.startsWith(" ") ? field.substring(1) : field);
            } else if (line.isEmpty() && !lines.isEmpty()) {
                try (JsonParser parser =
                        mapper.getFactory().createParser(String.join("\n", lines))) {
                    JsonNode event = mapper.readTree(parser);
                    if (parser.nextToken() != null)
                        throw new IllegalStateException("trailing JSON");
                    values.add(event.path("foo").asText() + "/" + event.path("bar").asText());
                } catch (com.fasterxml.jackson.core.JsonProcessingException ex) {
                    values.add("invalid");
                }
                lines.clear();
            }
        }
        return first.getResponse().getStatus() + ":" + values;
    }
}
