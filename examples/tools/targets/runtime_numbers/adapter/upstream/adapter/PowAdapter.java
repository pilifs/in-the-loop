package upstream.adapter;

import org.apache.commons.numbers.core.ArithmeticUtils;

/** The upstream-build check's adapter: it passes the two declared raw inputs to the original method, as the pinned
 * commit's own Maven build produced it, and returns its result. It maps nothing, catches nothing and replaces nothing.
 * Compiled separately against each revision's JAR. */
public final class PowAdapter {
    private PowAdapter() {
    }

    public static int pow(int k, int e) {
        return ArithmeticUtils.pow(k, e);
    }
}
