package datawork;

import java.util.Arrays;
import javaslang.collection.List;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) {
        for (int[][] rows : new int[][][]{{}, {{}}, {{1}}}) {
            List<List<Integer>> list = Matrices.list(rows);
            if (List.transpose(list) != list) throw new AssertionError("fast-path identity");
        }
        if (!Arrays.deepEquals(Matrices.observe(new int[][]{{1,2,3},{4,5,6}}), new int[][]{{1,4},{2,5},{3,6}}))
            throw new AssertionError("two by three");
        for (int code = 0; code < 400; code++) {
            int[][] rows = Matrices.cells(code);
            Object out;
            try { out = Matrices.observe(rows); }
            catch (IllegalArgumentException error) { out = error.getClass().getName(); }
            Object rectangle = null;
            if (Matrices.rectangular(rows)) {
                List<List<Integer>> input = Matrices.list(rows);
                boolean twice = rows.length == 0 || rows[0].length == 0 || List.transpose(List.transpose(input)).equals(input);
                rectangle = new Object[]{out, twice};
            }
            row(code, rows, fields("contract", out, "rectangle", rectangle),
                    fields("contract", Matrices.contract(code), "rectangle", Matrices.rectangle(code)));
        }
    }
}
