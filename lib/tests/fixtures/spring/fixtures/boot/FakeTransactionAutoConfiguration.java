package fixtures.boot;

import org.springframework.context.annotation.Configuration;
import org.springframework.transaction.annotation.EnableTransactionManagement;

/**
 * Shaped like Spring Boot's TransactionAutoConfiguration: the switch is on a nested configuration class. Listed in
 * the fixtures' META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports.
 */
@Configuration(proxyBeanMethods = false)
public class FakeTransactionAutoConfiguration {

    @Configuration(proxyBeanMethods = false)
    @EnableTransactionManagement
    public static class EnableTransactionManagementConfiguration {}
}
