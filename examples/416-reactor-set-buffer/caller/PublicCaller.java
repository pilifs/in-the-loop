import java.time.Duration;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

public class PublicCaller {
    static String buffers(List<HashSet<Integer>> emitted) {
        return emitted.stream().map(TreeSet::new).toList().toString();
    }
    public static String observe(String[] args) {
        boolean two = args[0].equals("two-requests");
        var input = two ? Flux.just(1, 1, 2, 1, 3) : args[0].equals("distinct") ? Flux.just(1, 2) : Flux.just(1, 1, 2);
        var emitted = new ArrayList<HashSet<Integer>>();
        var discarded = new ArrayList<Integer>();
        var first = new AtomicReference<String>();
        var flux = input.buffer(2, HashSet<Integer>::new).doOnDiscard(Integer.class, discarded::add)
                .doOnNext(emitted::add);
        StepVerifier.Step<HashSet<Integer>> steps = StepVerifier.create(flux, 1).consumeNextWith(v -> {});
        if (two) steps = steps.then(() -> first.set(buffers(emitted))).thenRequest(1).consumeNextWith(v -> {});
        String end;
        try {
            steps.expectComplete().verify(Duration.ofSeconds(2));
            end = "completed";
        } catch (AssertionError e) {
            if (!e.getMessage().contains("timed out")) throw e;
            end = "timeout";
        }
        if (!two) return end + "; buffers=" + buffers(emitted);
        return end + "; first=" + first.get() + "; buffers=" + buffers(emitted)
                + "; distinct=" + (emitted.size() == 2 && emitted.get(0) != emitted.get(1)) + "; discards=" + discarded;
    }
}
