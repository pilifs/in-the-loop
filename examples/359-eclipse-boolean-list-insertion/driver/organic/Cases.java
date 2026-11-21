package organic;

import org.eclipse.collections.impl.list.mutable.primitive.BooleanArrayList;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) {
        int code = 0;
        for (int source = 1; source <= 31; source++) {
            boolean[] old = InsertBits.bits(source);
            for (int bits = 1; bits <= 15; bits++) {
                boolean[] added = InsertBits.bits(bits);
                for (int index = -1; index <= old.length + 1; index++, code++) {
                    BooleanArrayList list = new BooleanArrayList(old);
                    String outcome;
                    try {
                        outcome = Boolean.toString(list.addAllAtIndex(index, added));
                    } catch (IndexOutOfBoundsException badIndex) {
                        outcome = "index-out-of-bounds";
                    }
                    boolean[] values = new boolean[list.size()];
                    for (int i = 0; i < values.length; i++) values[i] = list.get(i);
                    row(code, fields("source", old, "insert", added, "index", index),
                        fields("returns", outcome, "contents", fields("size", list.size(), "values", values)),
                        fields("returns", InsertBits.returns(code), "contents", InsertBits.contents(code)));
                }
            }
        }
    }
}
