import org.springframework.aop.framework.ProxyFactory;
import org.springframework.aop.retry.*;

import reactor.core.publisher.Mono;

import java.io.IOException;
import java.time.Duration;

public class PublicCaller {
    public static class Target {
        final boolean failFirst;
        int attempts;

        Target(boolean failFirst) {
            this.failFirst = failFirst;
        }

        public Mono<String> operation() {
            return Mono.defer(
                    () ->
                            ++attempts == 1 && failFirst
                                    ? Mono.error(new IOException("first"))
                                    : Mono.just("ok"));
        }
    }

    static String run(boolean failFirst, Duration delay, Duration jitter) {
        Target target = new Target(failFirst);
        var proxy = new ProxyFactory(target);
        var spec =
                new MethodRetrySpec((m, t) -> true, 3, delay, jitter, 1.5, Duration.ofMillis(50));
        proxy.addAdvice(new SimpleRetryInterceptor(spec));
        try {
            Mono<String> publisher = ((Target) proxy.getProxy()).operation();
            try {
                return publisher.block(Duration.ofSeconds(3)) + ":" + target.attempts;
            } catch (ArithmeticException duringSubscription) {
                return "subscription overflow:" + target.attempts;
            }
        } catch (ArithmeticException | IllegalArgumentException e) {
            return e.getClass().getSimpleName() + ":" + target.attempts;
        }
    }

    public static String observe(String[] args) {
        if (args[0].equals("small")) return run(false, Duration.ofMillis(10), Duration.ofMillis(5));
        String first =
                run(args[0].equals("oversized"), Duration.ofMillis(5), Duration.ofMillis(20));
        return args[0].equals("duration")
                ? first + "/" + run(false, Duration.ofMillis(5), Duration.ofDays(107000))
                : first;
    }
}
