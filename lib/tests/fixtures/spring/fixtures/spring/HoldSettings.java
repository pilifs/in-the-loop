package fixtures.spring;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** The configuration keys a module binds are a boundary too: a renamed key is a silent production change. */
@ConfigurationProperties("holds")
public record HoldSettings(int maxSeats, Duration ttl) {}
