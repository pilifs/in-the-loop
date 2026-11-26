import io.reactivex.rxjava3.core.Flowable;
import io.reactivex.rxjava3.core.Observable;
import io.reactivex.rxjava3.observables.GroupedObservable;

import java.util.ArrayList;
import java.util.List;

public class PublicCaller {
    static String failure(boolean backpressure) {
        var sentinel = new IllegalStateException("selector");
        List<String> keys = new ArrayList<>(), inner = new ArrayList<>(), outer = new ArrayList<>();
        List<Integer> values = new ArrayList<>();
        java.util.function.Function<Throwable, String> cause =
                t -> t == sentinel ? "same-error" : t.getClass().getName();
        if (backpressure) {
            Flowable.just(7)
                    .<String, Integer>groupBy(
                            v -> "K",
                            v -> {
                                throw sentinel;
                            })
                    .subscribe(
                            g -> {
                                keys.add(g.getKey());
                                g.subscribe(
                                        values::add,
                                        e -> inner.add(cause.apply(e)),
                                        () -> inner.add("complete"));
                            },
                            e -> outer.add(cause.apply(e)),
                            () -> outer.add("complete"));
        } else
            Observable.just(7)
                    .<String, Integer>groupBy(
                            v -> "K",
                            v -> {
                                throw sentinel;
                            })
                    .subscribe(
                            g -> {
                                keys.add(g.getKey());
                                g.subscribe(
                                        values::add,
                                        e -> inner.add(cause.apply(e)),
                                        () -> inner.add("complete"));
                            },
                            e -> outer.add(cause.apply(e)),
                            () -> outer.add("complete"));
        return keys.size()
                + "/"
                + String.join(",", keys)
                + "/"
                + values
                + "/"
                + String.join(",", inner)
                + "/"
                + String.join(",", outer);
    }

    public static String observe(String[] a) {
        if (a[0].equals("challenge")) return failure(true) + " / " + failure(false);
        boolean delayed = a[0].equals("intent");
        List<GroupedObservable<String, Integer>> groups = new ArrayList<>();
        List<Integer> values = new ArrayList<>();
        List<String> inner = new ArrayList<>(), outer = new ArrayList<>();
        java.util.function.Consumer<GroupedObservable<String, Integer>> join =
                g ->
                        g.subscribe(
                                values::add,
                                e -> inner.add(e.getClass().getName()),
                                () -> inner.add("complete"));
        (delayed ? Observable.just(7) : Observable.just(7, 8))
                .groupBy(v -> "K", v -> v)
                .subscribe(
                        g -> {
                            groups.add(g);
                            if (!delayed) join.accept(g);
                        },
                        e -> outer.add(e.getClass().getName()),
                        () -> outer.add("complete"));
        if (delayed) groups.forEach(join);
        String keys = String.join(",", groups.stream().map(GroupedObservable::getKey).toList());
        return (delayed ? "" : groups.size() + "/")
                + keys
                + "/"
                + values
                + "/"
                + String.join(",", inner)
                + "/"
                + String.join(",", outer);
    }
}
