package io.micrometer.signalfx;

import java.io.ByteArrayInputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.TimeUnit;
import java.util.zip.GZIPInputStream;
import com.sun.net.httpserver.HttpServer;
import com.signalfx.metrics.protobuf.SignalFxProtocolBuffers.*;
import io.micrometer.core.instrument.MockClock;
import io.micrometer.core.instrument.Timer;
import io.micrometer.core.instrument.simple.SimpleConfig;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;

public class UpgradeProbe {
    private static final Duration STEP = Duration.ofMinutes(1);
    private static Timer.Builder timer(boolean quantiles) {
        Timer.Builder timer = Timer.builder("latency").serviceLevelObjectives(Duration.ofMillis(1), Duration.ofMillis(10),
                Duration.ofMillis(100), Duration.ofSeconds(1)).distributionStatisticExpiry(Duration.ofMinutes(5))
                .distributionStatisticBufferLength(3).percentilePrecision(2);
        return quantiles ? timer.publishPercentiles(.95,.99) : timer;
    }
    private static double value(DataPoint point) {
        return point.getValue().hasDoubleValue() ? point.getValue().getDoubleValue() : point.getValue().getIntValue();
    }
    private static String label(DataPoint point, String key) {
        return point.getDimensionsList().stream().filter(d -> d.getKey().equals(key)).findFirst().orElseThrow().getValue();
    }
    private static String inspect(List<DataPoint> points, Timer reference, long time) {
        Map<Double,Long> buckets = new TreeMap<>();
        Map<Double,Double> gauges = new TreeMap<>();
        double count = -1, total = -1;
        for (DataPoint point : points) {
            if (point.getTimestamp() != time) throw new AssertionError("wrong publication timestamp");
            switch (point.getMetric()) {
                case "latency.count": count = value(point); break;
                case "latency.totalTime": total = value(point); break;
                case "latency.histogram":
                    String le = label(point, "le");
                    if (buckets.put(le.equals("+Inf") ? Double.POSITIVE_INFINITY : Double.valueOf(le), (long)value(point)) != null)
                        throw new AssertionError("duplicate upper bound");
                    break;
                case "latency.percentile":
                    if (point.getMetricType() != MetricType.GAUGE || gauges.put(Double.valueOf(label(point,"phi")),value(point)) != null)
                        throw new AssertionError("percentile type or duplicate label");
                    break;
                default: break;
            }
        }
        if (!buckets.keySet().equals(new java.util.TreeSet<>(List.of(.001,.01,.1,1.0,Double.POSITIVE_INFINITY))))
            throw new AssertionError("unexpected bucket labels " + buckets.keySet());
        for (var percentile : reference.takeSnapshot().percentileValues()) {
            Double actual = gauges.get(percentile.percentile());
            if (actual != null && Math.abs(actual - percentile.value(TimeUnit.SECONDS)) > 1e-9)
                throw new AssertionError("emitted percentile differs from the independent cumulative timer");
        }
        return (long)count + "/" + String.format(java.util.Locale.ROOT,"%.3f",total) + "/" + buckets.values() + "/" + gauges;
    }
    public static String observe(String[] args) throws Exception {
        boolean delta = args[0].equals("delta"), quantiles = !args[1].equals("none");
        HttpServer receiver = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
        List<DataPoint> captured = Collections.synchronizedList(new ArrayList<>());
        receiver.createContext("/", exchange -> {
            try (exchange) {
                byte[] body = exchange.getRequestBody().readAllBytes();
                if (body.length >= 2 && body[0] == (byte)0x1f && body[1] == (byte)0x8b)
                    try (var gzip = new GZIPInputStream(new ByteArrayInputStream(body))) { body = gzip.readAllBytes(); }
                captured.addAll(DataPointUploadMessage.parseFrom(body).getDatapointsList());
                exchange.sendResponseHeaders(200, -1);
            }
        });
        receiver.start();
        MockClock clock = new MockClock();
        SignalFxConfig config = new SignalFxConfig() {
            public String get(String key) { return null; }
            public boolean enabled() { return false; }
            public String accessToken() { return "local-fixture"; }
            public Duration step() { return STEP; }
            public String uri() { return "http://localhost:" + receiver.getAddress().getPort(); }
            public boolean publishDeltaHistogram() { return delta; }
            public boolean publishCumulativeHistogram() { return true; }
        };
        SignalFxMeterRegistry registry = new SignalFxMeterRegistry(config,clock);
        SimpleMeterRegistry control = new SimpleMeterRegistry(SimpleConfig.DEFAULT,clock);
        try {
            Timer subject = timer(quantiles).register(registry);
            Timer reference = timer(quantiles).register(control);
            List<String> history = new ArrayList<>();
            for (int step=0; step<2; step++) {
                int[] values = step == 1 && args[1].equals("vary") ? new int[]{5,5,5,2000} : new int[]{5,20,175,2000};
                for (int sample : values) {
                    subject.record(sample,TimeUnit.MILLISECONDS);
                    reference.record(sample,TimeUnit.MILLISECONDS);
                }
                clock.add(STEP);
                captured.clear();
                registry.publish();
                if (captured.isEmpty()) throw new AssertionError("no wire datapoints reached the loopback receiver");
                history.add(inspect(List.copyOf(captured), reference, clock.wallTime()));
            }
            return String.join("|", history);
        } finally { registry.close(); control.close(); receiver.stop(0); }
    }
}
