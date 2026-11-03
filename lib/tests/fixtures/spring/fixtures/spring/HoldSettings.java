package fixtures.spring;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * The configuration keys a module binds are a boundary too: a renamed key is a silent production change. A nested
 * type binds under its field's key, a list binds `key[0]`, `key[1]`, a map any key under its own.
 */
@ConfigurationProperties("holds")
public record HoldSettings(int maxSeats, Duration ttl, Region region, List<String> rows, Map<String, Integer> limits, Alerts alerts) {
    public record Alerts(boolean enabled, String channel) {}
}
