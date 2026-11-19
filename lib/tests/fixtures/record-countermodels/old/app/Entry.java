package app;

/** The previous version. Each method calls Shared.make(k) twice and reads the second call's array. */
public final class Entry {
    private Entry() {
    }

    /** The caller writes into the first call's array before the second call: the second array still holds k. */
    public static int stale(int k) {
        int[] first = Shared.make(k);
        first[0] = 99;
        int[] second = Shared.make(k);
        return second[0];
    }

    /**
     * The first call's array ends up in one local on one branch and in the other local on the other, beside a new
     * array of one cell, so the two paths number it differently at the join. The second call's array holds k.
     */
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
        int[] a;
        int[] b;
        int[] r = Shared.make(k);
        if (k % 2 == 0) {
            a = r;
            b = new int[1];
        } else {
            a = new int[1];
            b = r;
        }
        r = null;
        int[] second = Shared.make(k);
        return second[0] + a.length + b.length + bits - bits;
    }

    public static int branchText(int k) {
        String first = Shared.text(0);
        String second = Shared.text(1);
        String selected = (k & 1) == 0 ? first : second;
        return selected.equals(Shared.text(0)) ? 1 : 0;
    }

    public static void main(String[] args) {
        System.out.println("stale=" + stale(0) + " swapped=" + swapped(1) + " text=" + branchText(0) + "," + branchText(1));
    }
}
