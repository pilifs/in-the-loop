public final class QueueGrid {
    public static void main(String[] args) {
        int wrong = 0;
        for (int script = 0; script < 256; script++) {
            if (!QueueFill.queue(script)) throw new AssertionError(script);
            if (!QueueFill.fullMeansOccupied(script)) wrong++;
        }
        if (wrong == 0 || wrong == 256) throw new AssertionError(wrong);
        if (!QueueFill.covariant(true) || !QueueFill.covariant(false)) throw new AssertionError("covariance");
        for (int v : new int[]{0, 1, -1, Integer.MIN_VALUE, Integer.MAX_VALUE}) {
            if (!QueueFill.fill(v) || QueueFill.staleSurvives(v)) throw new AssertionError(v);
        }
        System.out.println("256 four-operation histories, " + wrong + " full/occupancy disagreements; fill and covariance held");
    }
}
