// A stand-in for the framework annotation of the same name, so that the fixtures compile without the framework on
// the class path. jvmcontract reads only the annotation's binary name and its elements, which are the real ones.
package org.springframework.transaction.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.TYPE, ElementType.METHOD})
public @interface Transactional {
    Propagation propagation() default Propagation.REQUIRED;
    boolean readOnly() default false;
    Class<? extends Throwable>[] rollbackFor() default {};
    String[] rollbackForClassName() default {};
    Class<? extends Throwable>[] noRollbackFor() default {};
}
