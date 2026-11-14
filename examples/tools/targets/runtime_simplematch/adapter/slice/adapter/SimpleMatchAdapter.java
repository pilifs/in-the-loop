package slice.adapter;

import org.springframework.util.PatternMatchUtils;

/** The runtime slice's adapter: it passes the two declared raw inputs to the original published method and returns
 * its result. It maps nothing, catches nothing and replaces nothing, so spring-core's own bytecode decides. Compiled
 * separately against each revision's JAR. */
public final class SimpleMatchAdapter {
    private SimpleMatchAdapter() {
    }

    public static boolean simpleMatch(String pattern, String str) {
        return PatternMatchUtils.simpleMatch(pattern, str);
    }
}
