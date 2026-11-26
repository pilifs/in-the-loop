import org.springframework.util.ConcurrentReferenceHashMap;

import java.lang.ref.Reference;
import java.util.*;

public class PublicCaller {
    static String run(String mode, int operation) {
        var map = new ConcurrentReferenceHashMap<String, String>(16, 1);
        map.put("a", "1");
        if (mode.equals("survivor")) map.put("b", "keep");
        var handles = new ArrayList<>(map.entrySet());
        int[] calls = {0};
        String next = mode.equals("replace") ? "2" : null;
        java.util.function.BiFunction<String, String, String> callback =
                (a, b) -> {
                    calls[0]++;
                    return next;
                };
        String val =
                switch (operation) {
                    case 0 -> map.compute("a", callback);
                    case 1 -> map.computeIfPresent("a", callback);
                    default -> map.merge("a", "2", callback);
                };
        int size = map.size();
        boolean empty = map.isEmpty();
        String stored = map.get("a");
        var entries =
                map.entrySet().stream().map(e -> e.getKey() + "=" + e.getValue()).sorted().toList();
        String result;
        if (mode.equals("survivor")) {
            calls[0] = 0;
            map.computeIfPresent("a", callback);
            result = size + ":" + empty + ":" + entries + ":" + calls[0];
        } else
            result = calls[0] + ":" + val + ":" + size + ":" + empty + ":" + stored + ":" + entries;
        Reference.reachabilityFence(handles);
        return result;
    }

    public static String observe(String[] args) {
        if (args[0].equals("survivor")) return run(args[0], 2);
        return run(args[0], 0) + " / " + run(args[0], 1) + " / " + run(args[0], 2);
    }
}
