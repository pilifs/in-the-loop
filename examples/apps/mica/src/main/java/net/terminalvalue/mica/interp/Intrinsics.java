package net.terminalvalue.mica.interp;

import java.util.OptionalDouble;

/**
 * The interpreter's substitutes for the native methods of the guest's {@code java.lang.StrictMath}: computed on
 * the host, by name, from a fixed list. The list is the whole of what guest code can make the host compute; a
 * name that is not on it is interpreted from the guest's own bytecode, or fails as unimplemented.
 */
public final class Intrinsics {

    private Intrinsics() {}

    /** The value of the unary function {@code name} of {@code java.lang.StrictMath} at {@code x}, if it is intrinsic. */
    public static OptionalDouble unary(String name, double x) {
        return switch (name) {
            case "sin" -> OptionalDouble.of(StrictMath.sin(x));
            case "cos" -> OptionalDouble.of(StrictMath.cos(x));
            case "tan" -> OptionalDouble.of(StrictMath.tan(x));
            case "sqrt" -> OptionalDouble.of(StrictMath.sqrt(x));
            case "log" -> OptionalDouble.of(StrictMath.log(x));
            case "exp" -> OptionalDouble.of(StrictMath.exp(x));
            default -> OptionalDouble.empty();
        };
    }
}
