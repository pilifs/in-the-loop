import org.reactivestreams.*;

import reactor.core.publisher.*;

import java.util.*;

public class PublicCaller {
    static String run(String arg, boolean hide) {
        IllegalStateException sentinel = new IllegalStateException("inner");
        Mono<Integer> inner = arg.equals("control") ? Mono.empty() : Mono.error(sentinel);
        Flux<Publisher<Integer>> outer =
                Flux.just(Flux.just(1, 2), hide ? inner.hide() : inner, Flux.just(3, 4));
        boolean step = arg.equals("challenge");
        Flux<Integer> flow =
                step ? outer.concatMapDelayError(p -> p, true, 32) : Flux.concatDelayError(outer);
        class Events implements Subscriber<Integer> {
            Subscription subscription;
            List<Integer> values = new ArrayList<>();
            List<String> terminal = new ArrayList<>();
            int demand = 0;
            boolean respected = true;

            public void onSubscribe(Subscription s) {
                subscription = s;
                if (!step) s.request(Long.MAX_VALUE);
            }

            public void onNext(Integer v) {
                if (step && values.size() >= demand) respected = false;
                values.add(v);
            }

            public void onError(Throwable e) {
                terminal.add(e == sentinel ? "same-error" : e.getClass().getName());
            }

            public void onComplete() {
                terminal.add("complete");
            }
        }
        Events e = new Events();
        flow.subscribe(e);
        if (step)
            for (int i = 0; i < 5 && e.terminal.isEmpty(); i++) {
                e.demand++;
                e.subscription.request(1);
            }
        return e.values
                + "/"
                + String.join(",", e.terminal)
                + (step ? "/demand=" + e.respected : "");
    }

    public static String observe(String[] a) {
        return run(a[0], false) + (a[0].equals("challenge") ? " / " + run(a[0], true) : "");
    }
}
