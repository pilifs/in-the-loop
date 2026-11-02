package net.terminalvalue.mica.rt;

import static net.terminalvalue.mica.Tests.equal;

public final class SymbolTableTest {

    private SymbolTableTest() {}

    public static void powersOfTwoAreTheirOwnSize() {
        for (int shift = 0; shift < 30; shift++) {
            equal(1 << shift, SymbolTable.tableSizeFor(1 << shift));
        }
    }

    public static void anythingElseRoundsUp() {
        equal(1, SymbolTable.tableSizeFor(0));
        equal(1, SymbolTable.tableSizeFor(-5));
        equal(4, SymbolTable.tableSizeFor(3));
        equal(16, SymbolTable.tableSizeFor(9));
        equal(1 << 20, SymbolTable.tableSizeFor((1 << 20) - 1));
    }

    public static void theMaximumIsACeiling() {
        equal(SymbolTable.MAXIMUM_CAPACITY, SymbolTable.tableSizeFor(SymbolTable.MAXIMUM_CAPACITY + 1));
        equal(SymbolTable.MAXIMUM_CAPACITY, SymbolTable.tableSizeFor(Integer.MAX_VALUE));
    }
}
