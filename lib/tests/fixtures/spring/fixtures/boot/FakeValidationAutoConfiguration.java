package fixtures.boot;

import org.springframework.boot.autoconfigure.condition.ConditionalOnResource;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.validation.beanvalidation.MethodValidationPostProcessor;

/** Shaped like Spring Boot's ValidationAutoConfiguration: applies when a Bean Validation provider is on the class path. */
@Configuration(proxyBeanMethods = false)
@ConditionalOnResource(resources = "classpath:META-INF/services/jakarta.validation.spi.ValidationProvider")
public class FakeValidationAutoConfiguration {

    @Bean
    public MethodValidationPostProcessor methodValidationPostProcessor() {
        return new MethodValidationPostProcessor();
    }
}
