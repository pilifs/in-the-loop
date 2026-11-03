// A stand-in for the framework type of the same name, so that the fixtures compile without the framework on the
// class path. jvmcontract reads only the binary names of the type and its members, which are the real ones.
package org.springframework.transaction.event;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
public @interface TransactionalEventListener {
    TransactionPhase phase() default TransactionPhase.AFTER_COMMIT;
    boolean fallbackExecution() default false;
    Class<?>[] value() default {};
    Class<?>[] classes() default {};
}
