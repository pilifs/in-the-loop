package gradebook;

public class ScoreSheet {
    public static int write(int[] scores, int slot, int score) {
        int previous = scores[slot];
        if (previous != score) {
            scores[slot] = score;
        }
        return previous;
    }
}
