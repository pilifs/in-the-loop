package com.fasterxml.jackson.annotation;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

@Retention(RetentionPolicy.RUNTIME)
public @interface JsonInclude {
    enum Include { ALWAYS, NON_NULL, NON_ABSENT, NON_EMPTY, NON_DEFAULT, CUSTOM, USE_DEFAULTS }
    Include value() default Include.ALWAYS;
}
