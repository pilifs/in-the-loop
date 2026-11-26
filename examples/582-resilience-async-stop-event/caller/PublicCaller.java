import io.github.resilience4j.retry.*;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public class PublicCaller {
    public static String observe(String[] a) throws Exception {
        String mode = a[0];
        var sentinel = new IllegalStateException("supplier");
        var calls = new AtomicInteger();
        var intervals = new AtomicInteger();
        var builder =
                RetryConfig.<String>custom()
                        .maxAttempts(3)
                        .intervalFunction(
                                attempt ->
                                        mode.equals("control")
                                                ? 1L
                                                : mode.equals("challenge")
                                                        ? -1L
                                                        : intervals.getAndIncrement() == 0
                                                                ? 0L
                                                                : -1L);
        if (mode.equals("challenge"))
            builder.retryOnResult("again"::equals).failAfterMaxAttempts(false);
        Retry retry = Retry.of("fixture", builder.build());
        var delays = new CopyOnWriteArrayList<Long>();
        var errors = new AtomicInteger();
        retry.getEventPublisher()
                .onRetry(e -> delays.add(e.getWaitInterval().toMillis()))
                .onError(e -> errors.incrementAndGet());
        var executor = Executors.newSingleThreadScheduledExecutor();
        try {
            var operation =
                    Retry.<String>decorateCompletionStage(
                            retry,
                            executor,
                            () -> {
                                int n = calls.incrementAndGet();
                                if (mode.equals("challenge"))
                                    return CompletableFuture.completedFuture("again");
                                if (mode.equals("control") && n == 2)
                                    return CompletableFuture.completedFuture("ok");
                                return CompletableFuture.failedFuture(sentinel);
                            });
            String result;
            try {
                result = operation.get().toCompletableFuture().get(5, TimeUnit.SECONDS);
            } catch (ExecutionException e) {
                result =
                        e.getCause() == sentinel ? "same-error" : e.getCause().getClass().getName();
            }
            return "calls=" + calls + ",retries=" + delays + ",errors=" + errors + "," + result;
        } finally {
            executor.shutdownNow();
        }
    }
}
