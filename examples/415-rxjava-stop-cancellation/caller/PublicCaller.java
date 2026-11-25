import java.util.concurrent.atomic.AtomicInteger;
import io.reactivex.observers.TestObserver;
import io.reactivex.processors.PublishProcessor;
import io.reactivex.subjects.*;

public class PublicCaller {
    static String events(TestObserver<Integer> t) {
        return "values=" + t.values() + " complete=" + t.completions() + " errors=" + t.errors().size();
    }
    public static String observe(String[] args) {
        var stop = PublishProcessor.<Integer>create();
        if (args[0].equals("shared")) {
            var a = MaybeSubject.<Integer>create();
            var b = MaybeSubject.<Integer>create();
            var ca = new AtomicInteger();
            var cb = new AtomicInteger();
            var first = a.takeUntil(stop.doOnCancel(ca::incrementAndGet)).test();
            var second = b.takeUntil(stop.doOnCancel(cb::incrementAndGet)).test();
            if (!a.hasObservers() || !b.hasObservers() || !stop.hasSubscribers()) throw new AssertionError("setup");
            first.dispose();
            first.dispose();
            String early = ca + "," + cb + "," + stop.hasSubscribers();
            stop.onNext(1);
            return "early=" + early + "; late=" + ca + "," + cb + "," + stop.hasSubscribers()
                    + "; mains=" + a.hasObservers() + "," + b.hasObservers() + "; first=" + events(first) + "; second=" + events(second);
        }
        var main = SingleSubject.<Integer>create();
        var sub = main.takeUntil(stop).test();
        String before = main.hasObservers() + "," + stop.hasSubscribers();
        if (args[0].equals("success")) main.onSuccess(7); else sub.dispose();
        return "attached=" + before + "; now=" + main.hasObservers() + "," + stop.hasSubscribers() + "; " + events(sub);
    }
}
