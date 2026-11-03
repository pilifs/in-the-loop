package com.fasterxml.jackson.annotation;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

@Retention(RetentionPolicy.RUNTIME)
public @interface JsonSubTypes {
    Type[] value();

    @Retention(RetentionPolicy.RUNTIME)
    @interface Type {
        Class<?> value();
        String name() default "";
    }
}
