import org.springframework.aop.framework.AopProxyUtils;
import org.springframework.beans.factory.support.*;
import org.springframework.resilience.annotation.*;

import java.util.concurrent.TimeUnit;

public class PublicCaller {
    public static class Service {
        int calls;

        private String immediate() {
            calls++;
            return "sent";
        }

        private String retry() {
            if (++calls == 1) throw new IllegalStateException("first");
            return "recovered";
        }

        @Retryable(delay = 1, timeUnit = TimeUnit.SECONDS)
        public String seconds() {
            return immediate();
        }

        @Retryable(delay = 1, timeUnit = TimeUnit.MINUTES)
        public String minutes() {
            return immediate();
        }

        @Retryable(delay = 1, maxDelay = 3, timeUnit = TimeUnit.SECONDS)
        public String finite() {
            return immediate();
        }

        @Retryable(
                maxRetries = 1,
                delay = 1,
                maxDelay = Long.MAX_VALUE / 2,
                timeUnit = TimeUnit.SECONDS)
        public String large() {
            return retry();
        }

        @Retryable(
                maxRetries = 1,
                delay = 1000,
                maxDelay = Long.MAX_VALUE,
                timeUnit = TimeUnit.MILLISECONDS)
        public String millis() {
            return retry();
        }
    }

    static String run(String name) {
        var factory = new DefaultListableBeanFactory();
        factory.registerBeanDefinition("service", new RootBeanDefinition(Service.class));
        var processor = new RetryAnnotationBeanPostProcessor();
        processor.setBeanFactory(factory);
        factory.addBeanPostProcessor(processor);
        var proxy = factory.getBean(Service.class);
        var target = (Service) AopProxyUtils.getSingletonTarget(proxy);
        try {
            String value =
                    switch (name) {
                        case "seconds" -> proxy.seconds();
                        case "minutes" -> proxy.minutes();
                        case "finite" -> proxy.finite();
                        case "large" -> proxy.large();
                        default -> proxy.millis();
                    };
            return value + ":" + target.calls;
        } catch (ArithmeticException e) {
            return e.getClass().getSimpleName() + ":" + target.calls;
        } finally {
            factory.destroySingletons();
        }
    }

    public static String observe(String[] args) {
        if (args[0].equals("units")) return run("seconds") + "/" + run("minutes");
        if (args[0].equals("finite")) return run("finite");
        return run("large") + "/" + run("millis");
    }
}
