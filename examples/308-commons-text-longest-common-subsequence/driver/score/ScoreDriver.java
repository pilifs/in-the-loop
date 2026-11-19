package score;

public final class ScoreDriver {
    public static void main(String[] args) {
        java.util.Set<String> words = new java.util.HashSet<>();
        for (int i = 0; i < 15; i++) {
            String word = LcsScore.word(i);
            if (word.length() > 3 || !word.matches("[ab]*") || !words.add(word)) {
                throw new AssertionError("invalid or repeated word at " + i);
            }
        }
        int differences = 0;
        for (int i = 0; i < 15; i++) {
            for (int j = 0; j < 15; j++) {
                String left = LcsScore.word(i);
                String right = LcsScore.word(j);
                int actual = LcsScore.score(i, j);
                if (args.length == 1 && args[0].equals("--observations")) {
                    System.out.printf("{\"left\":\"%s\",\"right\":\"%s\",\"score\":%d}%n", left, right, actual);
                }
                if (actual != ScoreOracle.expected(left, right)) {
                    differences++;
                }
            }
        }
        if (args.length == 0) {
            System.out.printf("{\"pairs\":225,\"disagreements\":%d,\"abAaScore\":%d}%n", differences, LcsScore.score(4, 3));
        }
    }
}
