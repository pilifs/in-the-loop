import org.apache.commons.collections4.collection.IndexedCollection;

import java.util.LinkedHashSet;
import java.util.concurrent.atomic.AtomicInteger;

public class IndexedAdds {
    public static String observe(String[] args) {
        var backing = new LinkedHashSet<String>();
        var calls = new AtomicInteger();
        var indexed =
                IndexedCollection.nonUniqueIndexedCollection(
                        backing,
                        text -> {
                            calls.incrementAndGet();
                            return Integer.valueOf(text);
                        });
        boolean first = indexed.add("01");
        int firstCalls = calls.get();
        boolean second = indexed.add(args[0].equals("duplicate") ? "01" : "2");
        return first
                + "/"
                + second
                + ", calls="
                + firstCalls
                + "/"
                + calls.get()
                + ", set="
                + backing
                + ", lookup="
                + indexed.get(1);
    }
}
