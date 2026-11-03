package net.terminalvalue.mica.rt;

/**
 * The sizing of the runtime's symbol table, an open-addressing hash table of the interned names and descriptors
 * whose capacity is a power of two, so that an index is a mask of the hash rather than a remainder.
 */
public final class SymbolTable {

    private SymbolTable() {}

    /** The largest capacity: the table index is a non-negative {@code int}, and a power of two at that. */
    public static final int MAXIMUM_CAPACITY = 1 << 30;

    /** The smallest power of two that is at least {@code cap}, between 1 and {@link #MAXIMUM_CAPACITY}. */
    public static int tableSizeFor(int cap) {
        int n = cap - 1;
        n |= n >>> 1;
        n |= n >>> 2;
        n |= n >>> 4;
        n |= n >>> 8;
        n |= n >>> 16;
        return (n < 0) ? 1 : (n >= MAXIMUM_CAPACITY) ? MAXIMUM_CAPACITY : n + 1;
    }
}
