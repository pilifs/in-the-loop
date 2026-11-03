package org.springframework.data.mongodb.repository;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

@Retention(RetentionPolicy.RUNTIME)
public @interface Query {
    String value() default "";
    String fields() default "";
    String sort() default "";
    boolean delete() default false;
}
