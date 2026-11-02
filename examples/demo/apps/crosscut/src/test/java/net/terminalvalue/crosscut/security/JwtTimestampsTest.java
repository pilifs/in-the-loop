package net.terminalvalue.crosscut.security;

import static net.terminalvalue.crosscut.Tests.check;
import static net.terminalvalue.crosscut.Tests.throwsIllegalArgument;
import static net.terminalvalue.crosscut.security.JwtTimestamps.valid;

public final class JwtTimestampsTest {

    private JwtTimestampsTest() {}

    public static void acceptsATokenInsideItsWindow() {
        check(valid(150, 100, 200, 0), "inside");
        check(valid(100, 100, 200, 0), "at not-before");
    }

    public static void rejectsATokenOutsideItsWindow() {
        check(!valid(50, 100, 200, 0), "before not-before");
        check(!valid(200, 100, 200, 0), "at expiry");
    }

    public static void toleratesSkewAfterExpiry() {
        check(valid(204, 100, 200, 5), "expired four seconds ago, five tolerated");
        check(!valid(205, 100, 200, 5), "expired five seconds ago, five tolerated");
    }

    public static void refusesANegativeSkew() {
        throwsIllegalArgument(() -> valid(150, 100, 200, -1));
    }
}
