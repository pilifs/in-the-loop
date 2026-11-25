import java.util.function.Predicate;
import java.util.function.Supplier;
import io.vavr.collection.Iterator;
import io.vavr.control.Option;

public class PublicCaller {
    static String search(Predicate<Integer> accept, Integer... values) {
        Option<Integer> selected = Iterator.of(values).findLast(accept);
        int[] calls = {0};
        Supplier<Integer> fallback = () -> { calls[0]++; return 99; };
        Integer value = selected.getOrElse(fallback);
        return selected.isDefined() + "/" + value + "/" + calls[0];
    }

    public static String observe(String[] args) {
        switch (args[0]) {
            case "null": return search(x -> x == null, null, 1, null);
            case "ordinary": return search(x -> x > 5, 1, 2, 3) + "," + search(x -> x % 2 == 1, 1, 2, 3);
            case "reorder":
                Predicate<Integer> accepts = x -> x == null || x == 7;
                return search(accepts, 7, null, 4) + "," + search(accepts, null, 7, 4)
                        + "," + search(accepts, 7, null, 4, 4) + "," + search(accepts, null, 7, 4, 4);
            default: throw new IllegalArgumentException(args[0]);
        }
    }
}
