import io.reactivex.Maybe;

import java.util.*;

public class PublicCaller {
    static String run(String mode, boolean iterable) {
        List<String> starts = new ArrayList<>();
        Maybe<Integer> one =
                Maybe.create(
                        e -> {
                            starts.add("first");
                            e.onSuccess(1);
                        });
        Maybe<Integer> two =
                Maybe.create(
                        e -> {
                            starts.add("second");
                            e.onSuccess(2);
                        });
        Maybe<Integer> empty =
                Maybe.defer(
                        () -> {
                            starts.add("empty");
                            return Maybe.empty();
                        });
        var flow =
                mode.equals("challenge")
                        ? (iterable
                                ? Maybe.concat(List.of(empty, one, two))
                                : Maybe.concatArray(empty, one, two))
                        : Maybe.concatArray(one, two);
        if (mode.equals("control")) {
            var t = flow.test();
            t.assertComplete().assertNoErrors();
            return t.values() + "/complete/" + starts;
        }
        var t = flow.firstElement().test();
        t.assertComplete().assertNoErrors();
        return t.values()
                + "/complete/"
                + (mode.equals("intent")
                        ? Collections.frequency(starts, "first")
                                + "/"
                                + Collections.frequency(starts, "second")
                        : starts);
    }

    public static String observe(String[] a) {
        return run(a[0], false) + (a[0].equals("challenge") ? " / " + run(a[0], true) : "");
    }
}
