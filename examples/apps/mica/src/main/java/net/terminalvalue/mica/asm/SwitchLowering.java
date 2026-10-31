package net.terminalvalue.mica.asm;

/**
 * How the assembler lowers a {@code switch} with the given case labels: to a {@code tableswitch}, which indexes a
 * table that spans the labels, or a {@code lookupswitch}, which searches the labels. The heuristic is javac's
 * ({@code com.sun.tools.javac.jvm.Gen.visitSwitch}): the table wins when its space, plus three times its time, is
 * no more than the lookup's, with space in words and time in comparisons.
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
}
