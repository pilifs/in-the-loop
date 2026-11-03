package fixtures.boot;

import io.micrometer.core.aop.TimedAspect;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** Shaped like Spring Boot's MetricsAspectsAutoConfiguration: the aspect needs the AspectJ weaver, which is not here. */
@Configuration(proxyBeanMethods = false)
@ConditionalOnClass(name = "org.aspectj.weaver.Advice")
public class FakeMetricsAutoConfiguration {

    @Bean
    public TimedAspect timedAspect() {
        return new TimedAspect();
    }
}
