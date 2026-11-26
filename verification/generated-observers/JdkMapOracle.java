import java.util.*;

/** Evaluator-only reference for the bounded public map history, using JDK collection views. */
public final class JdkMapOracle {
    public static void main(String[] args) {
        int maximum = Integer.parseInt(args[0]);
        boolean reverse = Boolean.parseBoolean(args[1]);
        int sentinel = Integer.parseInt(args[2]);
        for (int size = 0; size <= maximum; size++) {
            for (int subset = 0; subset < 1 << size; subset++) {
                final int mask = subset;
                Map<Integer,Integer> map = new HashMap<>();
                for (int i = 0; i < size; i++) {
                    int key = reverse ? size - 1 - i : i;
                    map.put(key, key);
                }
                map.put(null, sentinel);
                Set<Integer> retained = map.keySet();
                for (int step = 0; step < 2; step++) {
                    boolean flag = map.entrySet().removeIf(e -> e.getKey() != null && (mask & (1 << e.getKey())) != 0);
                    StringJoiner mappings = new StringJoiner(","), keys = new StringJoiner(",");
                    for (int k = 0; k < size; k++) {
                        if (map.containsKey(k)) mappings.add(k + "=" + map.get(k));
                        if (retained.contains(k)) keys.add(Integer.toString(k));
                    }
                    System.out.println(size + "/" + mask + "/" + step + "/" + flag + "/" + mappings + "/" +
                            keys + "/" + map.size() + "/" + retained.contains(null) + "/" + map.get(null));
                }
            }
        }
    }
}
