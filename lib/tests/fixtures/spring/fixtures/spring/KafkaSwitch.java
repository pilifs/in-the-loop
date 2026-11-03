package fixtures.spring;

import org.springframework.kafka.annotation.EnableKafka;

/** Carries the switch for @KafkaListener, but is not a component, so component scanning never registers it. */
@EnableKafka
public class KafkaSwitch {}
