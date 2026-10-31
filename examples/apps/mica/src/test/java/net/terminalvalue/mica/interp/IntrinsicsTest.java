package net.terminalvalue.mica.interp;

import static net.terminalvalue.mica.Tests.check;
import static net.terminalvalue.mica.Tests.equal;

import java.util.OptionalDouble;

public final class IntrinsicsTest {

    private IntrinsicsTest() {}

    public static void theListedFunctionsAreComputedOnTheHost() {
        equal(OptionalDouble.of(StrictMath.sin(1.0)), Intrinsics.unary("sin", 1.0));
        equal(OptionalDouble.of(3.0), Intrinsics.unary("sqrt", 9.0));
        equal(OptionalDouble.of(0.0), Intrinsics.unary("log", 1.0));
    }

    public static void anythingElseIsNotIntrinsic() {
        check(Intrinsics.unary("square", 4.0).isEmpty(), "square");
        check(Intrinsics.unary("random", 0.0).isEmpty(), "random");
    }
}
