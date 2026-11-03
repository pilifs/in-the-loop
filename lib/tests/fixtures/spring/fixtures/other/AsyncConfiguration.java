package fixtures.other;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;

/** Outside the scanned package and imported by nothing: its @EnableAsync is never read. */
@Configuration
@EnableAsync
public class AsyncConfiguration {}
