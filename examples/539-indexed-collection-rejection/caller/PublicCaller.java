import org.apache.commons.collections4.collection.IndexedCollection;

import java.util.*;

public class PublicCaller {
    public static String observe(String[] args) {
        List<String> base = new ArrayList<>();
        var index = IndexedCollection.uniqueIndexedCollection(base, Integer::valueOf);
        index.add("01");
        if (args[0].equals("control")) {
            index.add("2");
            return base + "/" + new ArrayList<>(index) + "/" + index.get(1) + "/" + index.get(2);
        }
        String error = "accepted";
        try {
            index.add("1");
        } catch (IllegalArgumentException e) {
            error = e.getClass().getSimpleName();
        }
        if (args[0].equals("intent"))
            return error + "/" + base + "/" + new ArrayList<>(index) + "/" + index.get(1);
        index.reindex();
        index.add("2");
        return "ok/" + base + "/" + index.get(1) + "/" + index.get(2);
    }
}
