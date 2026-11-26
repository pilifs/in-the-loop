import org.springframework.core.retry.*;
import org.springframework.core.retry.support.CompositeRetryListener;

import java.time.Duration;
import java.util.*;
import java.util.stream.Collectors;

public class PublicCaller {
    static final RuntimeException E0 = new IllegalStateException("first"),
            E1 = new IllegalArgumentException("retry");
    static final Object R = new Object();

    static String value(Object item) {
        return item == E0 ? "E0" : item == E1 ? "E1" : item == R ? "R" : "other";
    }

    static class Old implements RetryListener {
        final List<String> events = new ArrayList<>();

        public void onRetryFailure(RetryPolicy p, Retryable<?> r, Throwable t) {
            events.add("fail:" + value(t));
        }

        public void onRetrySuccess(RetryPolicy p, Retryable<?> r, Object v) {
            events.add("ok:" + value(v));
        }
    }

    static class Aware implements RetryListener {
        final List<String> events = new ArrayList<>();

        String history(RetryState s) {
            return s.getRetryCount()
                    + ":"
                    + s.getExceptions().stream()
                            .map(PublicCaller::value)
                            .collect(Collectors.joining(","));
        }

        public void onRetryFailure(RetryPolicy p, Retryable<?> r, RetryState state, Throwable t) {
            events.add("fail:" + value(t) + ":" + history(state));
        }

        public void onRetrySuccess(RetryPolicy p, Retryable<?> r, RetryState state, Object v) {
            events.add("ok:" + value(v) + ":" + history(state));
        }
    }

    static final RetryPolicy policy =
            RetryPolicy.builder().maxRetries(2).delay(Duration.ZERO).build();

    static String run(RetryListener listener, boolean immediate) throws RetryException {
        var template = new RetryTemplate(policy);
        template.setRetryListener(listener);
        int[] attempt = {0};
        return value(
                template.execute(
                        () -> {
                            if (!immediate && attempt[0]++ == 0) throw E0;
                            if (!immediate && attempt[0] == 2) throw E1;
                            return R;
                        }));
    }

    static String composite(boolean oldFirst) throws RetryException {
        Old old = new Old();
        Aware aware = new Aware();
        String result =
                run(
                        new CompositeRetryListener(
                                oldFirst ? List.of(old, aware) : List.of(aware, old)),
                        false);
        return Boolean.toString(
                result.equals("R")
                        && old.events.equals(List.of("fail:E1", "ok:R"))
                        && aware.events.equals(List.of("fail:E1:1:E0,E1", "ok:R:2:E0,E1")));
    }

    public static String observe(String[] args) throws RetryException {
        Old old = new Old();
        if (args[0].equals("direct")) {
            var composite = new CompositeRetryListener(List.of(old));
            Retryable<Object> op = () -> R;
            composite.onRetryFailure(policy, op, E1);
            composite.onRetrySuccess(policy, op, R);
            return old.events.toString();
        }
        if (args[0].equals("old")) {
            String result = run(old, false), events = old.events.toString();
            old.events.clear();
            run(old, true);
            return events + ":" + result + ":" + old.events;
        }
        try {
            RetryListener.class.getMethod(
                    "onRetryFailure",
                    RetryPolicy.class,
                    Retryable.class,
                    RetryState.class,
                    Throwable.class);
        } catch (NoSuchMethodException e) {
            return "absent";
        }
        if (args[0].equals("fanout")) return composite(true) + "/" + composite(false);
        Aware aware = new Aware();
        String result = run(aware, false);
        return aware.events + ":" + result;
    }
}
