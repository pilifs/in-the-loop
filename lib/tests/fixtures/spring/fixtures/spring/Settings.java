package fixtures.spring;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Service;

/** The other ways a class reads configuration: a placeholder with a default, a condition, and the Environment. */
@Service
@ConditionalOnProperty(prefix = "holds", name = "enabled", havingValue = "true")
public class Settings {
    @Value("${holds.retries:many}")
    int retries;

    private final Environment environment;

    public Settings(Environment environment) {
        this.environment = environment;
    }

    public String gateway() {
        return environment.getProperty("gateway.url", "http://localhost");
    }

    public Integer limit() {
        return environment.getProperty("gateway.limit", Integer.class);
    }

    public boolean hasToken() {
        return environment.containsProperty("gateway.token");
    }
}
