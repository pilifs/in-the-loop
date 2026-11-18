package lc;

import java.util.ArrayList;
import java.util.List;

/** A final static field holding an ArrayList (the checker's model of it runs only on request). */
public final class Listed {
    public static final List<String> ITEMS = new ArrayList<>();

    /** The list's size: 0 from a fresh class. */
    public static int items() {
        return ITEMS.size();
    }
}
