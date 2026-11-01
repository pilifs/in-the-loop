package net.terminalvalue.mica.asm;

import static net.terminalvalue.mica.Tests.check;
import static net.terminalvalue.mica.Tests.equal;
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

    public static void pairsAreSortedByKeyWithTheirOffsets() {
        int[] keys = {30, 10, 20};
        int[] offsets = {300, 100, 200};
        SwitchLowering.sortPairs(keys, offsets);
        equal(10, keys[0]);
        equal(20, keys[1]);
        equal(30, keys[2]);
        equal(100, offsets[0]);
        equal(200, offsets[1]);
        equal(300, offsets[2]);
    }

    public static void sortedPairsStayAsTheyAre() {
        int[] keys = {-5, 0, 7};
        int[] offsets = {1, 2, 3};
        SwitchLowering.sortPairs(keys, offsets);
        equal(-5, keys[0]);
        equal(7, keys[2]);
        equal(1, offsets[0]);
        equal(3, offsets[2]);
    }

    public static void everyKeyNeedsAnOffset() {
        throwsIllegalArgument(() -> SwitchLowering.sortPairs(new int[] {1, 2}, new int[] {1}));
    }
}
