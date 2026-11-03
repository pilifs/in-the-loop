package fixtures.shared;

import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Configuration;

/** Outside the scanned package, reached by the application class's @Import. */
@Configuration(proxyBeanMethods = false)
@EnableCaching
public class SharedConfiguration {}
