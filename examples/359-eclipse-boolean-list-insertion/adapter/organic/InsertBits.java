package organic;

import org.eclipse.collections.impl.list.mutable.primitive.BooleanArrayList;

public final class InsertBits {
    static int length(int word) { return 31 - Integer.numberOfLeadingZeros(word); }

    static boolean[] bits(int word) {
        int n = length(word);
        boolean[] values = new boolean[n];
        for (int i = 0; i < n; i++) values[i] = (word & (1 << (n - 1 - i))) != 0;
        return values;
    }

    static final class Input {
        final int index;
        final boolean[] original, inserted;

        Input(int code) {
            for (int word = 1; word <= 31; word++) {
                int slots = length(word) + 3;
                if (code < slots * 15) {
                    original = bits(word);
                    inserted = bits(1 + code / slots);
                    index = code % slots - 1;
                    return;
                }
                code -= slots * 15;
            }
            throw new IllegalArgumentException();
        }

        boolean valid() { return index >= 0 && index <= original.length; }
    }

    static final class Run {
        final Input input;
        final BooleanArrayList list;
        final int outcome;
        Run(int code) {
            input = new Input(code);
            list = new BooleanArrayList(input.original);
            int result;
            try {
                result = list.addAllAtIndex(input.index, input.inserted) ? 1 : 0;
            } catch (IndexOutOfBoundsException rejected) {
                result = -1;
            }
            outcome = result;
        }
    }

    public static int returns(int code) {
        Run r = new Run(code);
        int expected = !r.input.valid() ? -1 : r.input.inserted.length == 0 ? 0 : 1;
        return r.outcome == expected ? 1 : 0;
    }

    public static int contents(int code) {
        Run r = new Run(code);
        Input x = r.input;
        int added = x.valid() ? x.inserted.length : 0;
        if (r.list.size() != x.original.length + added) return 0;
        for (int i = 0; i < r.list.size(); i++) {
            boolean bit;
            if (!x.valid() || i < x.index) bit = x.original[i];
            else if (i < x.index + added) bit = x.inserted[i - x.index];
            else bit = x.original[i - added];
            if (r.list.get(i) != bit) return 0;
        }
        return 1;
    }
}
