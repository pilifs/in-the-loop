import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.slf4j.LoggerFactory;
import org.springframework.boot.Banner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.context.annotation.Configuration;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

public class PublicCaller {
    @Configuration(proxyBeanMethods = false) static class Config {}
    static final JsonMapper READER = JsonMapper.builder().enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build();
    static String typed(JsonNode node) {
        if (node == null) return "missing";
        if (node.isString()) return "string:" + node.asString();
        if (node.isNumber()) return "number:" + node;
        return node.toString();
    }
    public static String observe(String[] args) throws Exception {
        boolean mixed = args[0].equals("challenge");
        Number[] values = switch (args[0]) {
            case "intent" -> new Number[] {Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY,
                    Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY};
            case "control" -> new Number[] {1.25d, -2.5f};
            case "challenge" -> new Number[] {Double.NaN};
            default -> throw new IllegalArgumentException(args[0]);
        };
        var output = new ByteArrayOutputStream();
        PrintStream saved = System.out;
        try (var ps = new PrintStream(output, true, StandardCharsets.UTF_8)) {
            System.setOut(ps);
            var app = new SpringApplication(Config.class);
            app.setWebApplicationType(WebApplicationType.NONE);
            app.setBannerMode(Banner.Mode.OFF);
            try (var context = app.run("--logging.structured.format.console=ecs")) {
                var logger = LoggerFactory.getLogger("sample.events");
                for (int i = 0; i < values.length; i++) {
                    var event = logger.atInfo().addKeyValue("ratio", values[i]);
                    if (mixed) event.addKeyValue("samples", new double[] {1.0, Double.NaN});
                    event.log("typed-sample-" + i);
                }
            }
        } finally { System.setOut(saved); }
        var rows = output.toString(StandardCharsets.UTF_8).lines().filter(s -> s.contains("typed-sample-")).toList();
        if (rows.size() != values.length) throw new AssertionError("wrong number of ECS events " + rows.size());
        List<String> results = new ArrayList<>();
        for (int i = 0; i < rows.size(); i++) {
            try {
                var json = READER.readTree(rows.get(i));
                if (!("typed-sample-" + i).equals(json.path("message").asString())) throw new AssertionError("event order");
                String result = typed(json.get("ratio"));
                if (mixed) {
                    var samples = json.path("samples");
                    result += samples.isArray() && samples.size() == 2 ? "/[" + typed(samples.get(0)) + "," + typed(samples.get(1)) + "]" : "/bad-array";
                }
                results.add(result);
            } catch (JacksonException malformed) { results.add("invalid-json"); }
        }
        return String.join(",", results);
    }
}
