import java.util.List;
import java.util.Optional;
import org.jooq.lambda.Seq;
import org.jooq.lambda.Window;

public class PublicCaller {
    static String endpoint(Optional<Integer> v) { return v.map(String::valueOf).orElse("-"); }
    static String pair(Window<Integer> w) { return endpoint(w.firstValue()) + ":" + endpoint(w.lastValue()); }
    static List<String> pairs(long lower, long upper) {
        return Seq.of(1, 2, 3).window(lower, upper).map(PublicCaller::pair).toList();
    }
    public static String observe(String[] args) {
        long lower = args[0].equals("future") ? 1 : -5;
        if (args[0].equals("overflow"))
            return "5=" + pairs(-5, 5).get(2) + "; max-1=" + pairs(-5, Long.MAX_VALUE - 1).get(2);
        var frames = Seq.of(1, 2, 3).window(lower, 5).map(w -> w.window().toList()).toList();
        return pairs(lower, 5) + "; frames=" + frames;
    }
}
