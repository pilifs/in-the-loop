package org.springframework.data.mongodb.core.mapping;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

@Retention(RetentionPolicy.RUNTIME)
public @interface Field {
    String value() default "";
    String name() default "";
}
