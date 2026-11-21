package organic;

import com.google.common.collect.HashMultiset;
import com.google.common.collect.Multiset;
import com.google.common.collect.Multisets;
import java.util.Iterator;
import java.util.NoSuchElementException;

public final class SumView {
    static int operand(int i) {
        switch (i) {
            case 0: return 0;
            case 1: return 1;
            case 2: return 3;
            case 3: return (1 << 30) - 1;
            case 4: return 1 << 30;
            case 5: return (1 << 30) + 1;
            default: return Integer.MAX_VALUE;
        }
    }

    static Multiset<String> view(int left, int right) {
        HashMultiset<String> a = HashMultiset.create();
        HashMultiset<String> b = HashMultiset.create();
        a.add("a", left);
        b.add("a", right);
        return Multisets.sum(a, b);
    }

    static int expected(int code) {
        long n = (long) operand(code / 7) + operand(code % 7);
        return n > Integer.MAX_VALUE ? Integer.MAX_VALUE : (int) n;
    }

    static boolean exhausted(Iterator<?> entries) {
        if (entries.hasNext()) return false;
        try {
            entries.next();
            return false;
        } catch (NoSuchElementException exhausted) {
            return true;
        }
    }

    public static int lookup(int code) {
        return view(operand(code / 7), operand(code % 7)).count("a") == expected(code) ? 1 : 0;
    }

    public static int size(int code) {
        return view(operand(code / 7), operand(code % 7)).size() == expected(code) ? 1 : 0;
    }

    public static int absent(int code) {
        return view(operand(code / 7), operand(code % 7)).count("missing") == 0 ? 1 : 0;
    }

    public static int entries(int code) {
        Iterator<Multiset.Entry<String>> it = view(operand(code / 7), operand(code % 7)).entrySet().iterator();
        int count = expected(code);
        if (count == 0) return exhausted(it) ? 1 : 0;
        try {
            if (!it.hasNext()) return 0;
            Multiset.Entry<String> e = it.next();
            return "a".equals(e.getElement()) && e.getCount() == count && exhausted(it) ? 1 : 0;
        } catch (IllegalArgumentException invalidCount) {
            return 0;
        }
    }

    public static int live(int code) {
        HashMultiset<String> a = HashMultiset.create();
        HashMultiset<String> b = HashMultiset.create();
        a.add("a", 3);
        b.add("a", 3);
        Multiset<String> sum = Multisets.sum(a, b);
        if (sum.count("a") != 6 || sum.size() != 6 || sum.entrySet().iterator().next().getCount() != 6) return 0;
        a.add("a");
        return sum.count("a") == 7 && sum.size() == 7 && sum.entrySet().iterator().next().getCount() == 7 ? 1 : 0;
    }
}
