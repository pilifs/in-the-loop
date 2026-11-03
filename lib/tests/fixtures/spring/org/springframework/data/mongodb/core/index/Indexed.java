package org.springframework.data.mongodb.core.index;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

@Retention(RetentionPolicy.RUNTIME)
public @interface Indexed {
    boolean unique() default false;
}
