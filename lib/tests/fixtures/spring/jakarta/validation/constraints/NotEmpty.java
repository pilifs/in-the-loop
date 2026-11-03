// A stand-in for the framework annotation of the same name, so that the fixtures compile without the framework on
// the class path. jvmcontract reads only the annotation's binary name and its elements, which are the real ones.
package jakarta.validation.constraints;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.FIELD, ElementType.METHOD, ElementType.PARAMETER, ElementType.TYPE_USE})
public @interface NotEmpty {
    Class<?>[] groups() default {};
}
