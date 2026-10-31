package net.terminalvalue.mica.interp;

import static net.terminalvalue.mica.Tests.equal;

public final class LookupSwitchTest {

    private LookupSwitchTest() {}

    private static final int[] MATCHES = {-1000, -7, 0, 3, 4, 100, 65535, Integer.MAX_VALUE};

    public static void everyMatchIsFound() {
        for (int i = 0; i < MATCHES.length; i++) {
            equal(i, LookupSwitch.find(MATCHES, MATCHES[i]));
        }
    }

    public static void aMissingKeyTakesTheDefault() {
        equal(-1, LookupSwitch.find(MATCHES, 5));
        equal(-1, LookupSwitch.find(MATCHES, Integer.MIN_VALUE));
        equal(-1, LookupSwitch.find(new int[0], 0));
    }

    public static void theMidpointIsBetweenTheBounds() {
        equal(5, LookupSwitch.midpoint(3, 8));
        equal(3, LookupSwitch.midpoint(3, 3));
        equal(0, LookupSwitch.midpoint(0, 1));
    }
}
