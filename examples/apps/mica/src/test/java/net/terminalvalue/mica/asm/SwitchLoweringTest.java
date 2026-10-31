package net.terminalvalue.mica.asm;

import static net.terminalvalue.mica.Tests.check;
import static net.terminalvalue.mica.Tests.throwsIllegalArgument;

public final class SwitchLoweringTest {

    private SwitchLoweringTest() {}

    public static void denseLabelsUseATable() {
        check(SwitchLowering.useTable(0, 9, 10), "0..9");
        check(SwitchLowering.useTable(1, 3, 3), "1..3");
        check(SwitchLowering.useTable(-1, 2, 3), "three labels in a range of four");
    }

    public static void sparseLabelsUseALookup() {
        check(!SwitchLowering.useTable(0, 1000, 2), "0 and 1000");
        check(!SwitchLowering.useTable(0, 20, 3), "three labels in a range of twenty-one");
    }

    public static void aSingleLabelUsesALookup() {
        check(!SwitchLowering.useTable(5, 5, 1), "one label");
    }

    public static void aSwitchNeedsALabelAndARange() {
        throwsIllegalArgument(() -> SwitchLowering.useTable(0, 9, 0));
        throwsIllegalArgument(() -> SwitchLowering.useTable(9, 0, 1));
        throwsIllegalArgument(() -> SwitchLowering.useTable(0, 100_000, 8191));
    }
}
