package datawork;

import java.util.Arrays;
import java.util.IdentityHashMap;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static int[] aliases(String[][] rows) {
        int[] result = new int[rows.length];
        for (int i = 0; i < rows.length; i++) {
            int first = 0;
            while (rows[first] != rows[i]) first++;
            result[i] = first;
        }
        return result;
    }

    static Object[] identity(String[][] rows) {
        int[] before = aliases(rows);
        String[][] copy = Arrays.stream(rows).map(String[]::clone).toArray(String[][]::new);
        Integer[][] out = RowMapper.parseRows(rows), next = RowMapper.parseRows(rows);
        int pairs = 0;
        boolean separate = out != next, isolated = true;
        for (int i = 0; i < out.length; i++) {
            for (int j = 0; j < out.length; j++) {
                if (j < i && out[i] != out[j]) pairs++;
                separate &= out[i] != next[j] && (i == j || next[i] != next[j]);
            }
            for (int j = 0; j < out[i].length; j++) {
                Integer old = out[i][j];
                out[i][j] = 407;
                for (int k = 0; k < out.length; k++)
                    if (k != i) isolated &= Arrays.equals(out[k], next[k]);
                isolated &= old.equals(next[i][j]);
                out[i][j] = old;
            }
        }
        return new Object[]{pairs, separate, isolated, Arrays.equals(before, aliases(rows)) && Arrays.deepEquals(copy, rows)};
    }

    static void regression() {
        String[] a = {"-2","bad",null,"2147483648","+7"}, e = {};
        String[][] f = {a, a, a.clone(), e, e, new String[0], {"+7"}, {"bad","-2"}};
        Integer[][] values = RowMapper.parseRows(f);
        if (!Arrays.equals(values[0], new Integer[]{-2,0,0,0,7}) || !RowMapper.correct(f, values)
                || !Arrays.equals(identity(f), new Object[]{28,true,true,true})) throw new AssertionError("eight-row fixture");
        IdentityHashMap<String[],Integer[]> memo = new IdentityHashMap<>();
        Integer[][] wrong = Arrays.stream(f).map(r -> memo.computeIfAbsent(r,
                x -> RowMapper.parseRows(new String[][]{x})[0])).toArray(Integer[][]::new);
        if (!RowMapper.correct(f, wrong) || RowMapper.isolated(f, f.clone(), RowMapper.copyContents(f), wrong, values))
            throw new AssertionError("value-correct memoizer escaped the identity claim");
    }

    public static void main(String[] args) {
        regression();
        for (int code = 0; code < 187; code++) {
            String[][] rows = RowMapper.input(code);
            row(code, fields("rows", rows, "aliases", aliases(rows)),
                    fields("values", RowMapper.parseRows(rows), "fresh", identity(rows)),
                    fields("values", RowChecks.values(code), "fresh", RowChecks.fresh(code)));
        }
    }
}
