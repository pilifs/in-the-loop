package fixtures.boot;

import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.annotation.EnableKafka;

/** Shaped like Spring Boot's KafkaAutoConfiguration, whose condition fails here: the Kafka client is not on the class path. */
@Configuration(proxyBeanMethods = false)
@ConditionalOnClass(name = "org.apache.kafka.clients.consumer.ConsumerRecord")
public class FakeKafkaAutoConfiguration {

    @Configuration(proxyBeanMethods = false)
    @EnableKafka
    public static class EnableKafkaConfiguration {}
}
