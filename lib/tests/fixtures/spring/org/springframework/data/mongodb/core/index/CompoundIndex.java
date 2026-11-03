package org.springframework.data.mongodb.core.index;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

@Retention(RetentionPolicy.RUNTIME)
public @interface CompoundIndex {
    String def() default "";
    String name() default "";
}
