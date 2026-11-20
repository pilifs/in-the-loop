package optionalgrid;

import java.util.function.Supplier;
public final class Fallback implements Supplier<Integer> {
    public int calls;
    public Integer get(){calls++;return 7;}
}
