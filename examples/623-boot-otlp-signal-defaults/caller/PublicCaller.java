import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.zip.GZIPInputStream;
import com.google.protobuf.CodedInputStream;
import com.google.protobuf.WireFormat;
import com.sun.net.httpserver.HttpServer;
import io.micrometer.registry.otlp.OtlpMeterRegistry;
import io.micrometer.tracing.Tracer;
import io.opentelemetry.api.logs.Severity;
import io.opentelemetry.sdk.logs.SdkLoggerProvider;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.micrometer.metrics.autoconfigure.MetricsAutoConfiguration;
import org.springframework.boot.micrometer.metrics.autoconfigure.export.otlp.OtlpMetricsExportAutoConfiguration;
import org.springframework.boot.micrometer.observation.autoconfigure.ObservationAutoConfiguration;
import org.springframework.boot.micrometer.tracing.autoconfigure.MicrometerTracingAutoConfiguration;
import org.springframework.boot.micrometer.tracing.opentelemetry.autoconfigure.OpenTelemetryTracingAutoConfiguration;
import org.springframework.boot.micrometer.tracing.opentelemetry.autoconfigure.otlp.OtlpTracingAutoConfiguration;
import org.springframework.boot.opentelemetry.autoconfigure.OpenTelemetrySdkAutoConfiguration;
import org.springframework.boot.opentelemetry.autoconfigure.logging.OpenTelemetryLoggingAutoConfiguration;
import org.springframework.boot.opentelemetry.autoconfigure.logging.otlp.OtlpLoggingAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

public class PublicCaller {
    record Request(String path,List<String> headers,String encoding,byte[] bytes) {}
    // Only length-delimited children along the specified OTLP message path are selected.
    static List<byte[]> fields(byte[] bytes, int... numbers) throws IOException {
        List<byte[]> level = List.of(bytes);
        for (int field : numbers) {
            var next = new ArrayList<byte[]>();
            for (byte[] message : level) {
                var input = CodedInputStream.newInstance(message);
                for (int tag; (tag=input.readTag()) != 0;) {
                    if (WireFormat.getTagFieldNumber(tag) == field && WireFormat.getTagWireType(tag) == 2)
                        next.add(input.readByteArray());
                    else input.skipField(tag);
                }
            }
            level = next;
        }
        return level;
    }
    static boolean includes(byte[] bytes,String text,int... path) throws IOException {
        return fields(bytes,path).stream().anyMatch(b -> text.equals(new String(b,StandardCharsets.UTF_8)));
    }
    static boolean counter(byte[] bytes) throws IOException {
        for (byte[] metric : fields(bytes,1,2,2)) {
            if (!includes(metric,"springfixture",1)) continue;
            for (byte[] point : fields(metric,7,1)) {
                var in = CodedInputStream.newInstance(point);
                for (int tag; (tag=in.readTag()) != 0;) {
                    if (tag == (4 << 3 | 1)) { if (in.readDouble() == 7.0) return true; }
                    else if (tag == (6 << 3 | 1)) { if (in.readSFixed64() == 7) return true; }
                    else in.skipField(tag);
                }
            }
        }
        return false;
    }
    static String decode(Request request) throws IOException {
        byte[] bytes = request.bytes();
        if (request.encoding().equals("gzip")) {
            try (var gzip = new GZIPInputStream(new ByteArrayInputStream(bytes))) { bytes = gzip.readAllBytes(); }
        }
        String marker;
        if (request.path().equals("/explicit") || request.path().endsWith("/logs")) {
            if (!includes(bytes,"Hello",1,2,2,5,1)) return null;
            marker = "Hello";
        } else if (request.path().endsWith("/traces")) {
            if (!includes(bytes,"fixture-span",1,2,2,5)) return null;
            marker = "fixture-span";
        } else if (request.path().endsWith("/metrics")) {
            if (!counter(bytes)) return null;
            marker = "springfixture=7";
        } else return null;
        return request.path() + ":" + request.headers() + ":" + request.encoding() + ":" + marker;
    }
    public static String observe(String[] args) throws Exception {
        var pending = new LinkedBlockingQueue<Request>();
        var server = HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/", exchange -> {
            try {
                var headers = exchange.getRequestHeaders();
                pending.add(new Request(exchange.getRequestURI().getPath(),List.copyOf(headers.getOrDefault("suite",List.of())),
                        Optional.ofNullable(headers.getFirst("Content-Encoding")).orElse("plain"),exchange.getRequestBody().readAllBytes()));
                exchange.getResponseHeaders().set("Content-Type","application/x-protobuf");
                exchange.sendResponseHeaders(200,-1);
            } finally { exchange.close(); }
        });
        server.start();
        try {
            String base = "http://127.0.0.1:" + server.getAddress().getPort();
            boolean control = args[0].equals("control");
            var configurations = new ArrayList<Class<?>>(List.of(OpenTelemetrySdkAutoConfiguration.class,
                    OpenTelemetryLoggingAutoConfiguration.class,OtlpLoggingAutoConfiguration.class));
            var props = new ArrayList<String>();
            if (control) props.add("management.opentelemetry.logging.export.otlp.endpoint=" + base + "/explicit");
            else {
                configurations.addAll(List.of(ObservationAutoConfiguration.class,MicrometerTracingAutoConfiguration.class,
                        OpenTelemetryTracingAutoConfiguration.class,OtlpTracingAutoConfiguration.class,
                        MetricsAutoConfiguration.class,OtlpMetricsExportAutoConfiguration.class));
                props.addAll(List.of("management.opentelemetry.otlp.endpoint=" + base,"management.opentelemetry.otlp.compression=gzip",
                        "management.opentelemetry.otlp.headers.suite=common","management.tracing.sampling.probability=1.0",
                        "management.otlp.metrics.export.step=1s"));
                if (args[0].equals("challenge")) props.addAll(List.of("management.opentelemetry.logging.export.otlp.compression=none",
                        "management.opentelemetry.logging.export.otlp.headers.suite=logs"));
            }
            var answer = new AtomicReference<String>();
            new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(configurations.toArray(Class<?>[]::new)))
                    .withPropertyValues(props.toArray(String[]::new)).run(ctx -> {
                var logs = ctx.getBean(SdkLoggerProvider.class);
                logs.get("fixture").logRecordBuilder().setSeverity(Severity.INFO).setBody("Hello").setTimestamp(Instant.now()).emit();
                logs.forceFlush().join(4,TimeUnit.SECONDS);
                if (!control) {
                    ctx.getBean(Tracer.class).nextSpan().name("fixture-span").start().end();
                    ctx.getBean(SdkTracerProvider.class).forceFlush().join(4,TimeUnit.SECONDS);
                    ctx.getBean(OtlpMeterRegistry.class).counter("springfixture").increment(7);
                }
                List<String> wanted = control ? List.of("/explicit") : List.of("/v1/logs","/v1/traces","/v1/metrics");
                var results = new HashMap<String,String>();
                long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(9);
                while (System.nanoTime() < end && !results.keySet().containsAll(wanted)) {
                    var req = pending.poll(200,TimeUnit.MILLISECONDS);
                    if (req == null) continue;
                    String value = decode(req);
                    if (value != null) results.putIfAbsent(req.path(),value);
                }
                answer.set(String.join("/",wanted.stream().map(path -> results.getOrDefault(path,path + ":missing")).toList()));
            });
            return answer.get();
        } finally { server.stop(0); }
    }
}
