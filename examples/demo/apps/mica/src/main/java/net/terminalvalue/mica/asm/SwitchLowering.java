package net.terminalvalue.mica.asm;

/**
 * How the assembler lowers a {@code switch} with the given case labels: to a {@code tableswitch}, which indexes a
 * table that spans the labels, or a {@code lookupswitch}, which searches the labels. The heuristic is javac's
 * ({@code com.sun.tools.javac.jvm.Gen.visitSwitch}): the table wins when its space, plus three times its time, is
 * no more than the lookup's, with space in words and time in comparisons. A {@code lookupswitch} also needs its
 * match-offset pairs sorted by match value (JVMS §6.5), which javac does for the cases of a {@code switch} and an
 * assembler does here for the cases it is given in source order.
 */
public final class SwitchLowering {

    private SwitchLowering() {}

    /**
     * @param lo     the smallest case label
     * @param hi     the largest case label
     * @param labels how many case labels there are: at least one, and no more than the 8190 match-offset pairs a
     *               {@code lookupswitch} can hold in a {@code Code} attribute
     */
    public static boolean useTable(int lo, int hi, int labels) {
        if (labels < 1 || labels > 8190 || lo > hi) {
            throw new IllegalArgumentException("a switch needs a label, at most 8190 of them, and a range");
        }
        long tableSpaceCost = 4 + ((long) hi - lo + 1); // words
        long tableTimeCost = 3; // comparisons
        long lookupSpaceCost = 3 + 2 * (long) labels;
        long lookupTimeCost = labels;
        return tableSpaceCost + 3 * tableTimeCost <= lookupSpaceCost + 3 * lookupTimeCost;
    }

    /**
     * Sorts the match-offset pairs of a {@code lookupswitch} by match value, in place, each offset staying with
     * its key: an insertion sort, linear on pairs that are already sorted, which the cases of a {@code switch} in
     * source order usually are.
     *
     * @throws IllegalArgumentException when there are not as many offsets as keys
     */
    public static void sortPairs(int[] keys, int[] offsets) {
        if (keys.length != offsets.length) {
            throw new IllegalArgumentException("every key needs an offset");
        }
        for (int i = 1; i < keys.length; i++) {
            int key = keys[i];
            int offset = offsets[i];
            int j = i;
            while (j > 0 && keys[j - 1] > key) {
                keys[j] = keys[j - 1];
                offsets[j] = offsets[j - 1];
                j--;
            }
            keys[j] = key;
            offsets[j] = offset;
        }
    }
}
