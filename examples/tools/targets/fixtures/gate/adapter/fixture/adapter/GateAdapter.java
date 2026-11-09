package fixture.adapter;

import fixture.Gate;

/** A minimal adapter: it takes the declared raw input, calls the original method and exposes its outcome. It maps
 * nothing, catches nothing and replaces nothing, so the original bytecode decides. Compiled separately against each
 * revision's JAR. */
public final class GateAdapter {
    private GateAdapter() {
    }

    public static boolean allowed(int code) {
        return Gate.allowed(code);
    }
}
