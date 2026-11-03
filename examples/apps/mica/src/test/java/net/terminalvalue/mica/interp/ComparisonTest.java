package net.terminalvalue.mica.interp;

import static net.terminalvalue.mica.Tests.equal;

public final class ComparisonTest {

    private ComparisonTest() {}

    public static void longsCompareByValue() {
        equal(-1, Comparison.lcmp(1L, 2L));
        equal(0, Comparison.lcmp(2L, 2L));
        equal(1, Comparison.lcmp(Long.MAX_VALUE, Long.MIN_VALUE));
    }

    public static void floatsCompareByValue() {
        equal(-1, Comparison.fcmp(1.0f, 2.0f, true));
        equal(0, Comparison.fcmp(2.0f, 2.0f, false));
        equal(1, Comparison.fcmp(3.0f, 2.0f, false));
        equal(-1, Comparison.dcmp(1.0, 2.0, true));
        equal(1, Comparison.dcmp(3.0, 2.0, false));
    }

    public static void negativeZeroEqualsZero() {
        equal(0, Comparison.fcmp(-0.0f, 0.0f, true));
        equal(0, Comparison.dcmp(0.0, -0.0, false));
    }

    public static void infinitiesAreOrdered() {
        equal(-1, Comparison.fcmp(Float.NEGATIVE_INFINITY, Float.MAX_VALUE, false));
        equal(1, Comparison.dcmp(Double.POSITIVE_INFINITY, Double.MAX_VALUE, false));
    }

    public static void theGFormPushesOneForNaN() {
        equal(1, Comparison.fcmp(Float.NaN, 1.0f, true));
        equal(1, Comparison.fcmp(1.0f, Float.NaN, true));
        equal(1, Comparison.dcmp(Double.NaN, Double.NaN, true));
    }
}
