import reactor.core.publisher.*;

import java.util.*;

public class PublicCaller {
    public static String observe(String[] a) {
        var sentinel = new IllegalArgumentException("second");
        var receiver =
                Flux.concat(
                        Flux.just("a"),
                        a[0].equals("challenge") ? Flux.<String>error(sentinel) : Flux.just("b"));
        if (a[0].equals("control")) receiver = receiver.hide();
        int[] entered = {0};
        List<String> values = new ArrayList<>(), terminal = new ArrayList<>();
        receiver.thenMany(
                        Flux.defer(
                                () -> {
                                    entered[0]++;
                                    return Flux.just("c");
                                }))
                .subscribe(
                        values::add,
                        e -> terminal.add(e == sentinel ? "same-error" : e.getClass().getName()),
                        () -> terminal.add("complete"));
        return values
                + "/"
                + String.join(",", terminal)
                + (a[0].equals("challenge") ? "/tail=" + entered[0] : "");
    }
}
