import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import jakarta.json.bind.Jsonb;
import jakarta.json.bind.JsonbBuilder;
import kotlinx.serialization.json.Json;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.http.converter.autoconfigure.*;
import org.springframework.boot.test.context.FilteredClassLoader;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.ApplicationContext;
import org.springframework.http.MediaType;
import org.springframework.http.converter.*;
import org.springframework.http.converter.HttpMessageConverters;
import org.springframework.http.converter.json.*;
import org.springframework.mock.http.MockHttpOutputMessage;

public class PublicCaller {
    static HttpMessageConverters list(ApplicationContext ctx, boolean client) {
        if (client) {
            var b = HttpMessageConverters.forClient().registerDefaults();
            ctx.getBeanProvider(ClientHttpMessageConvertersCustomizer.class).orderedStream().forEach(c -> c.customize(b));
            return b.build();
        }
        var b = HttpMessageConverters.forServer().registerDefaults();
        ctx.getBeanProvider(ServerHttpMessageConvertersCustomizer.class).orderedStream().forEach(c -> c.customize(b));
        return b.build();
    }
    @SuppressWarnings("unchecked")
    static String write(HttpMessageConverters list) throws Exception {
        for (var candidate : list) {
            if (!candidate.canWrite(Map.class, MediaType.APPLICATION_JSON)) continue;
            var out = new MockHttpOutputMessage();
            ((HttpMessageConverter<Object>) candidate).write(Map.of("answer", 7), MediaType.APPLICATION_JSON, out);
            try (var reader = jakarta.json.Json.createReader(new java.io.ByteArrayInputStream(out.getBodyAsBytes()))) {
                var obj = reader.readObject();
                String selected = candidate instanceof JsonbHttpMessageConverter ? "jsonb" : candidate.getClass().getSimpleName();
                return selected + ":" + (obj.size() == 1 ? obj.getInt("answer") : "extra");
            }
        }
        return "none";
    }
    public static String observe(String[] args) throws Exception {
        boolean onlyKotlin = args[0].equals("control");
        var hidden = new ArrayList<>(List.of("tools.jackson", "com.fasterxml.jackson", "com.google.gson"));
        if (onlyKotlin) hidden.addAll(List.of("jakarta.json.bind", "org.eclipse.yasson"));
        try (var loader = new FilteredClassLoader(hidden.toArray(String[]::new))) {
            var runner = new ApplicationContextRunner().withClassLoader(loader)
                    .withConfiguration(AutoConfigurations.of(HttpMessageConvertersAutoConfiguration.class))
                    .withBean(Json.class, () -> Json.Default);
            if (!onlyKotlin) runner = runner.withBean(Jsonb.class, JsonbBuilder::create);
            var result = new AtomicReference<String>();
            runner.run(ctx -> {
                var server = list(ctx, false);
                if (args[0].equals("challenge")) result.set(write(server) + "/" + write(list(ctx, true)));
                else {
                    boolean jsonb = false;
                    Boolean kotlin = null;
                    for (var c : server) {
                        if (c instanceof JsonbHttpMessageConverter) jsonb = true;
                        if (c instanceof KotlinSerializationJsonHttpMessageConverter) kotlin = c.canWrite(Map.class, MediaType.APPLICATION_JSON);
                    }
                    result.set(kotlin + ":" + jsonb);
                }
            });
            return result.get();
        }
    }
}
