package gradebook;

public class ScoreSheet {
    public static int write(int[] scores, int slot, int score) {
        int previous = scores[slot];
        if (slot < scores.length - 1) {
            scores[slot] = score;
        }
        return previous;
    }
}
