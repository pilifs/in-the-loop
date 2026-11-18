package app;

/** The new version: what the checker takes the previous version to give. */
public final class Entry {
    private Entry() {
    }

    /** 99, which is what the previous version's first array holds when its second call is made. */
    public static int stale(int k) {
        int[] second = Shared.make(k);
        return 99;
    }

    /** k on one branch only, 0 on the other: what a fresh array of one cell holds. */
    public static int swapped(int k) {
        // 30 independent branches first: the checker merges paths only once it has explored 512, and merges
        // heaps, numbering each path's objects in the order its state reaches them, only past 1024 (`merge_after`,
        // `merge_heaps_after`).
        int bits = 0;
        if ((k & 1) != 0) {
            bits++;
        }
        if ((k & 2) != 0) {
            bits++;
        }
        if ((k & 4) != 0) {
            bits++;
        }
        if ((k & 8) != 0) {
            bits++;
        }
        if ((k & 16) != 0) {
            bits++;
        }
        if ((k & 32) != 0) {
            bits++;
        }
        if ((k & 64) != 0) {
            bits++;
        }
        if ((k & 128) != 0) {
            bits++;
        }
        if ((k & 256) != 0) {
            bits++;
        }
        if ((k & 512) != 0) {
            bits++;
        }
        if ((k & 1024) != 0) {
            bits++;
        }
        if ((k & 2048) != 0) {
            bits++;
        }
        if ((k & 4096) != 0) {
            bits++;
        }
        if ((k & 8192) != 0) {
            bits++;
        }
        if ((k & 16384) != 0) {
            bits++;
        }
        if ((k & 32768) != 0) {
            bits++;
        }
        if ((k & 65536) != 0) {
            bits++;
        }
        if ((k & 131072) != 0) {
            bits++;
        }
        if ((k & 262144) != 0) {
            bits++;
        }
        if ((k & 524288) != 0) {
            bits++;
        }
        if ((k & 1048576) != 0) {
            bits++;
        }
        if ((k & 2097152) != 0) {
            bits++;
        }
        if ((k & 4194304) != 0) {
            bits++;
        }
        if ((k & 8388608) != 0) {
            bits++;
        }
        if ((k & 16777216) != 0) {
            bits++;
        }
        if ((k & 33554432) != 0) {
            bits++;
        }
        if ((k & 67108864) != 0) {
            bits++;
        }
        if ((k & 134217728) != 0) {
            bits++;
        }
        if ((k & 268435456) != 0) {
            bits++;
        }
        if ((k & 536870912) != 0) {
            bits++;
        }
        int[] second = Shared.make(k);
        return (k % 2 == 0 ? second[0] : 0) + 2 + bits - bits;
    }

    public static void main(String[] args) {
        System.out.println("stale=" + stale(0) + " swapped=" + swapped(1));
    }
}
