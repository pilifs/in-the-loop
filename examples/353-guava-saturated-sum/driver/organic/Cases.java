package organic;

import com.google.common.collect.HashMultiset;
import com.google.common.collect.Multiset;
import com.google.common.collect.Multisets;
import java.util.Iterator;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static Object entry(Multiset<String> sum) {
        Iterator<Multiset.Entry<String>> it = sum.entrySet().iterator();
        try {
            if (!it.hasNext()) return fields("key", null, "count", 0, "exhausted", SumView.exhausted(it));
            Multiset.Entry<String> e = it.next();
            return fields("key", e.getElement(), "count", e.getCount(), "exhausted", SumView.exhausted(it));
        } catch (IllegalArgumentException e) {
            return e.getClass().getName();
        }
    }

    static int[] observe(Multiset<String> sum) {
        return new int[]{sum.size(), sum.count("a"), sum.entrySet().iterator().next().getCount()};
    }

    static Object mutation() {
        HashMultiset<String> a = HashMultiset.create();
        HashMultiset<String> b = HashMultiset.create();
        a.add("a", 3);
        b.add("a", 3);
        Multiset<String> sum = Multisets.sum(a, b);
        int[] before = observe(sum);
        a.add("a");
        return new int[][]{before, observe(sum)};
    }

    public static void main(String[] args) {
        for (int code = 0; code < 49; code++) {
            int a = SumView.operand(code / 7), b = SumView.operand(code % 7);
            Multiset<String> sum = SumView.view(a, b);
            row(code, fields("left", a, "right", b),
                fields("lookup", sum.count("a"), "size", sum.size(), "entries", entry(sum),
                       "absent", sum.count("missing"), "live", mutation()),
                fields("lookup", SumView.lookup(code), "size", SumView.size(code), "entries", SumView.entries(code),
                       "absent", SumView.absent(code), "live", SumView.live(code)));
        }
    }
}
