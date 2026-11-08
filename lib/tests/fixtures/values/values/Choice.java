package values;

import java.util.List;

/**
 * VF-023's case (verification/findings.md): a list that is one of two lists made on different branches, whose size
 * stock JBMC 6.11.0 refutes, dispatching size() to the wrong class or to java.util.List.size()'s stub. On the JVM
 * oneOrTwo(n) is n for n of 1 and 2.
 */
public final class Choice {
    private Choice() {
    }

    public static int oneOrTwo(int n) {
        Object a = new Object(), b = new Object();
        List<Object> l = n == 1 ? List.of(a) : List.of(a, b);
        return l.size();
    }
}
