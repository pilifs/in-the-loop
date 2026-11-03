package com.fasterxml.jackson.annotation;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

/** Stand-in for Jackson's annotation, with the elements the tool reads. */
@Retention(RetentionPolicy.RUNTIME)
public @interface JsonTypeInfo {
    enum Id { NONE, CLASS, MINIMAL_CLASS, NAME, SIMPLE_NAME, DEDUCTION, CUSTOM }
    enum As { PROPERTY, WRAPPER_OBJECT, WRAPPER_ARRAY, EXTERNAL_PROPERTY, EXISTING_PROPERTY }
    Id use();
    As include() default As.PROPERTY;
    String property() default "";
}
