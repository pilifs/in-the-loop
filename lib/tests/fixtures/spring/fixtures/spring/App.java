package fixtures.spring;

import fixtures.shared.SharedConfiguration;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Import;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * The application class: component scanning covers this package, the imported configuration brings its own
 * switches, and the auto-configurations the class path's imports file lists apply. There is no @EnableAsync in
 * scope ({@link fixtures.other.AsyncConfiguration} is outside the scanned package), no @EnableMethodSecurity at
 * all, and the @EnableKafka of {@link KafkaSwitch} is on a class that is not a component.
 */
@SpringBootApplication
@Import(SharedConfiguration.class)
@EnableScheduling
public class App {}
