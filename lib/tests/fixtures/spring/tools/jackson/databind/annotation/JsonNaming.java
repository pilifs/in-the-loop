package tools.jackson.databind.annotation;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

/** Jackson 3's naming-strategy annotation lives in databind, not in the annotations package. */
@Retention(RetentionPolicy.RUNTIME)
public @interface JsonNaming {
    Class<?> value();
}
