package org.springframework.kafka.annotation;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

@Retention(RetentionPolicy.RUNTIME)
public @interface KafkaListener {
    String[] topics() default {};
}
