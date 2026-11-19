package gradebook;

public class ScoreSheet {
    public static int write(int[] scores, int slot, int score) {
        int previous = scores[slot];
        scores[slot] = score;
        return previous;
    }
}
