package datawork;

import java.util.Arrays;
import org.apache.commons.lang3.math.NumberUtils;

public final class RowMapper {
    public static Integer[][] parseRows(String[][] rows) {
        return Arrays.stream(rows)
                .map(row -> Arrays.stream(row).map(NumberUtils::toInt).toArray(Integer[]::new))
                .toArray(Integer[][]::new);
    }

    public static String token(int id) {
        return switch (id) { case 0 -> "-2"; case 1 -> "bad"; case 2 -> null; case 3 -> "2147483648"; default -> "+7"; };
    }

    public static String[] word(int id) {
        if (id == 0) return new String[0];
        if (id <= 5) return new String[]{token(id - 1)};
        return new String[]{token((id - 6) / 5), token((id - 6) % 5)};
    }

    public static String[][] input(int code) {
        if (code == 0) return new String[0][];
        int id = (code - 1) % 31;
        String[] a = word(id), b = word((id + 5) % 31);
        return switch ((code - 1) / 31) {
            case 0 -> new String[][]{a};
            case 1 -> new String[][]{a, a};
            case 2 -> new String[][]{a, a.clone()};
            case 3 -> new String[][]{a, b, a};
            case 4 -> new String[][]{a, a.clone(), b};
            default -> new String[][]{a, b, word((id + 6) % 31)};
        };
    }

    /** This grammar uses magnitude and range; the library's parser has no part in its result. */
    public static int expected(String text) {
        if (text == null || text.isEmpty()) return 0;
        boolean neg = text.charAt(0) == '-';
        int i = neg || text.charAt(0) == '+' ? 1 : 0;
        if (i == text.length()) return 0;
        long n = 0, limit = neg ? 2147483648L : 2147483647L;
        for (; i < text.length(); i++) {
            int d = text.charAt(i) - '0';
            if (d < 0 || d > 9 || n > (limit - d) / 10) return 0;
            n = n * 10 + d;
        }
        return (int) (neg ? -n : n);
    }

    public static boolean correct(String[][] input, Integer[][] output) {
        if (input.length != output.length) return false;
        for (int i = 0; i < input.length; i++) {
            if (output[i] == null || input[i].length != output[i].length) return false;
            for (int j = 0; j < input[i].length; j++)
                if (output[i][j] == null || output[i][j].intValue() != expected(input[i][j])) return false;
        }
        return true;
    }

    public static boolean isolated(String[][] rows, String[][] originals, String[][] contents,
                                   Integer[][] first, Integer[][] second) {
        if (first == second || first.length != rows.length || second.length != rows.length) return false;
        for (int i = 0; i < rows.length; i++) {
            if (first[i] == null || second[i] == null || first[i].length != contents[i].length
                    || second[i].length != contents[i].length || rows[i] != originals[i]) return false;
            for (int j = 0; j < rows.length; j++)
                if (first[i] == second[j] || (i != j && (first[i] == first[j] || second[i] == second[j]))) return false;
            for (int j = 0; j < first[i].length; j++) {
                first[i][j] = 407;
                if (second[i][j] == null || second[i][j].intValue() != expected(contents[i][j])) return false;
            }
        }
        for (int i = 0; i < rows.length; i++)
            for (int j = 0; j < contents[i].length; j++) if (contents[i][j] != rows[i][j]) return false;
        return true;
    }

    public static String[][] copyContents(String[][] rows) {
        String[][] copy = new String[rows.length][];
        for (int i = 0; i < copy.length; i++) copy[i] = rows[i].clone();
        return copy;
    }

}
