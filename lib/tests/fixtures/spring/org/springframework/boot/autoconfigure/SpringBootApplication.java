// A stand-in for the framework annotation of the same name, so that the fixtures compile without the framework on
// the class path. jvmcontract reads only the annotation's binary name, its elements and its meta-annotations, which
// are the real ones.
package org.springframework.boot.autoconfigure;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.context.annotation.ComponentScan;

@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.TYPE})
@SpringBootConfiguration
@EnableAutoConfiguration
@ComponentScan
public @interface SpringBootApplication {
    Class<?>[] exclude() default {};

    String[] excludeName() default {};

    String[] scanBasePackages() default {};

    Class<?>[] scanBasePackageClasses() default {};
}
