import org.eclipse.collections.api.block.HashingStrategy;
import org.eclipse.collections.api.map.MutableMap;
import org.eclipse.collections.impl.map.mutable.UnifiedMap;
import org.eclipse.collections.impl.map.strategy.mutable.UnifiedMapWithHashingStrategy;

import java.util.*;

public class PublicCaller {
    static MutableMap<Integer, Integer> map(boolean strategy, boolean collide) {
        if (!strategy) return new UnifiedMap<>();
        return new UnifiedMapWithHashingStrategy<>(
                new HashingStrategy<Integer>() {
                    public int computeHashCode(Integer k) {
                        return collide ? 1 : k.hashCode();
                    }

                    public boolean equals(Integer a, Integer b) {
                        return Objects.equals(a, b);
                    }
                });
    }

    static String entries(MutableMap<Integer, Integer> m) {
        Map<Integer, Integer> copy = new TreeMap<>();
        for (var e : m.entrySet()) copy.put(e.getKey(), e.getValue());
        return copy.toString();
    }

    static String run(String arg, boolean strategy) {
        var m = map(strategy, arg.equals("challenge"));
        RuntimeException sentinel = new RuntimeException("callback");
        if (arg.equals("control")) {
            int[] calls = {0};
            m.put(4, 9);
            int result =
                    m.updateValue(
                            4,
                            () -> {
                                calls[0]++;
                                return 5;
                            },
                            v -> v + 1);
            return result + "/" + calls[0] + "/" + entries(m);
        }
        boolean same = false;
        if (arg.equals("challenge")) {
            m.put(1, 7);
            try {
                m.updateValueWith(
                        4,
                        () -> 5,
                        (v, p) -> {
                            throw sentinel;
                        },
                        2);
            } catch (RuntimeException error) {
                same = error == sentinel;
            }
            String before = entries(m);
            int value = m.updateValueWith(4, () -> 5, Integer::sum, 2);
            return same + "/" + before + "/" + value + "/" + entries(m);
        }
        try {
            m.updateValue(
                    4,
                    () -> {
                        throw sentinel;
                    },
                    v -> v + 1);
        } catch (RuntimeException e) {
            same = e == sentinel;
        }
        String state =
                "same="
                        + same
                        + ",size="
                        + m.size()
                        + ",key="
                        + m.containsKey(4)
                        + ",entries="
                        + entries(m);
        try {
            return state + ";retry=" + m.updateValue(4, () -> 5, v -> v + 1) + "/" + entries(m);
        } catch (RuntimeException e) {
            return state + ";retry=" + e.getClass().getSimpleName();
        }
    }

    public static String observe(String[] args) {
        return args[0].equals("challenge")
                ? run(args[0], true)
                : run(args[0], false) + " / " + run(args[0], true);
    }
}
