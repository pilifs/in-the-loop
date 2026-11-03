// A stand-in for the framework class of the same name, so that the fixtures compile without the framework on the
// class path. jvmcontract reads only the binary names of the class and its methods, which are the real ones.
package org.springframework.web.service.annotation;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

@Retention(RetentionPolicy.RUNTIME)
public @interface HttpExchange {
    String value() default "";
    String method() default "";
}
