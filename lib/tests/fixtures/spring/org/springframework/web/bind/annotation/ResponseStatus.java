// A stand-in for the framework annotation of the same name, so that the fixtures compile without the framework on
// the class path. jvmcontract reads only the annotation's binary name and its elements, which are the real ones.
package org.springframework.web.bind.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
import org.springframework.http.HttpStatus;

@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.TYPE, ElementType.METHOD})
public @interface ResponseStatus {
    HttpStatus value() default HttpStatus.INTERNAL_SERVER_ERROR;
    HttpStatus code() default HttpStatus.INTERNAL_SERVER_ERROR;
    String reason() default "";
}
