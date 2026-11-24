import java.time.Duration;
import java.util.concurrent.TimeUnit;
import io.micrometer.core.instrument.MockClock;
import io.micrometer.core.instrument.Timer;
import io.micrometer.core.instrument.simple.SimpleConfig;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;

public class QuantileReference {
    public static void main(String[] args) {
        for (boolean vary : new boolean[]{false,true}) {
            MockClock clock = new MockClock();
            SimpleMeterRegistry registry = new SimpleMeterRegistry(SimpleConfig.DEFAULT, clock);
            try {
                Timer timer = Timer.builder("reference").serviceLevelObjectives(Duration.ofMillis(1), Duration.ofMillis(10),
                        Duration.ofMillis(100), Duration.ofSeconds(1)).distributionStatisticExpiry(Duration.ofMinutes(5))
                        .distributionStatisticBufferLength(3).percentilePrecision(2).publishPercentiles(.95,.99).register(registry);
                for (int step = 0; step < 2; step++) {
                    int[] samples = vary && step == 1 ? new int[]{5,5,5,2000} : new int[]{5,20,175,2000};
                    for (int sample : samples) timer.record(sample, TimeUnit.MILLISECONDS);
                    clock.add(Duration.ofMinutes(1));
                    for (var percentile : timer.takeSnapshot().percentileValues())
                        System.out.println(vary + "/" + step + "/" + percentile.percentile() + "/" + percentile.value(TimeUnit.SECONDS));
                }
            } finally { registry.close(); }
        }
    }
}
