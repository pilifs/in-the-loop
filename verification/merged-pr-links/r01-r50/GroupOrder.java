import io.reactivex.rxjava3.core.Observable;

import java.util.ArrayList;
import java.util.concurrent.atomic.AtomicReference;

public class GroupOrder {
    public static String observe(String[] args) {
        var phase = new AtomicReference<>("initial");
        var events = new ArrayList<String>();
        Observable.just(7)
                .groupBy(
                        item -> "K",
                        item -> {
                            events.add("select");
                            return phase.get() + "-" + item;
                        })
                .subscribe(
                        group -> {
                            events.add("group:" + group.getKey());
                            if (args[0].equals("change")) phase.set("published");
                            group.subscribe(
                                    v -> events.add("value:" + v),
                                    e -> events.add("inner-error"),
                                    () -> events.add("inner-complete"));
                        },
                        e -> events.add("outer-error"),
                        () -> events.add("outer-complete"));
        return events.toString();
    }
}
