import static org.intheloop.controls.Grid.*;

public final class Cases {
    private static int[][] shared() { int[] row = {1}; return new int[][] {row, row}; }

    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "RaggedProof#reversed", "arguments", new String[]{"null"}),
                fields("holds", RaggedProof.reversed(null)), fields());
        row(1, fields("entry", "RaggedProof#reversed", "arguments", new String[]{"new int[0][]"}),
                fields("holds", RaggedProof.reversed(new int[0][])), fields());
        row(2, fields("entry", "RaggedProof#reversed", "arguments", new String[]{"new int[][]{new int[0],null}"}),
                fields("holds", RaggedProof.reversed(new int[][]{new int[0],null})), fields());
        row(3, fields("entry", "RaggedProof#reversed", "arguments", new String[]{"new int[][]{new int[]{1},new int[]{1}}"}),
                fields("holds", RaggedProof.reversed(new int[][]{new int[]{1},new int[]{1}})), fields());
        row(4, fields("entry", "RaggedProof#wrong", "arguments", new String[]{"null"}),
                fields("holds", RaggedProof.wrong(null)), fields());
        row(5, fields("entry", "RaggedProof#wrong", "arguments", new String[]{"new int[0][]"}),
                fields("holds", RaggedProof.wrong(new int[0][])), fields());
        row(6, fields("entry", "RaggedProof#wrong", "arguments", new String[]{"new int[][]{new int[0],null}"}),
                fields("holds", RaggedProof.wrong(new int[][]{new int[0],null})), fields());
        row(7, fields("entry", "RaggedProof#iter", "arguments", new String[]{"null"}),
                fields("holds", RaggedProof.iter(null)), fields());
        row(8, fields("entry", "RaggedProof#iter", "arguments", new String[]{"new int[0][]"}),
                fields("holds", RaggedProof.iter(new int[0][])), fields());
        row(9, fields("entry", "RaggedProof#iter", "arguments", new String[]{"new int[][]{new int[0],null}"}),
                fields("holds", RaggedProof.iter(new int[][]{new int[0],null})), fields());
        row(10, fields("entry", "RaggedProof#iter", "arguments", new String[]{"new int[][]{new int[]{1},new int[]{1}}"}),
                fields("holds", RaggedProof.iter(new int[][]{new int[]{1},new int[]{1}})), fields());
        row(11, fields("entry", "RaggedProof#snapshot", "arguments", new String[]{"null"}),
                fields("holds", RaggedProof.snapshot(null)), fields());
        row(12, fields("entry", "RaggedProof#snapshot", "arguments", new String[]{"new int[0][]"}),
                fields("holds", RaggedProof.snapshot(new int[0][])), fields());
        row(13, fields("entry", "RaggedProof#snapshot", "arguments", new String[]{"new int[][]{new int[0],null}"}),
                fields("holds", RaggedProof.snapshot(new int[][]{new int[0],null})), fields());
        row(14, fields("entry", "RaggedProof#distinct", "arguments", new String[]{"null"}),
                fields("holds", RaggedProof.distinct(null)), fields());
        row(15, fields("entry", "RaggedProof#distinct", "arguments", new String[]{"new int[0][]"}),
                fields("holds", RaggedProof.distinct(new int[0][])), fields());
        row(16, fields("entry", "RaggedProof#distinct", "arguments", new String[]{"new int[][]{new int[0],null}"}),
                fields("holds", RaggedProof.distinct(new int[][]{new int[0],null})), fields());
        row(17, fields("entry", "RaggedProof#distinct", "arguments", new String[]{"new int[][]{new int[]{1},new int[]{1}}"}),
                fields("holds", RaggedProof.distinct(new int[][]{new int[]{1},new int[]{1}})), fields());
        row(18, fields("entry", "RaggedProof#distinct", "arguments", new String[]{"shared()"}),
                fields("holds", RaggedProof.distinct(shared())), fields());
        row(19, fields("entry", "RowIdentities#nonNullOuter", "arguments", new String[]{"new int[0][]"}),
                fields("holds", RowIdentities.nonNullOuter(new int[0][])), fields());
        row(20, fields("entry", "RowIdentities#nonNullOuter", "arguments", new String[]{"null"}),
                fields("holds", RowIdentities.nonNullOuter(null)), fields());
        row(21, fields("entry", "RowIdentities#noEmptyOuter", "arguments", new String[]{"null"}),
                fields("holds", RowIdentities.noEmptyOuter(null)), fields());
        row(22, fields("entry", "RowIdentities#noEmptyOuter", "arguments", new String[]{"new int[0][]"}),
                fields("holds", RowIdentities.noEmptyOuter(new int[0][])), fields());
        row(23, fields("entry", "RowIdentities#noDistinctEqualRows", "arguments", new String[]{"new int[][]{new int[0],null}"}),
                fields("holds", RowIdentities.noDistinctEqualRows(new int[][]{new int[0],null})), fields());
        row(24, fields("entry", "RowIdentities#noDistinctEqualRows", "arguments", new String[]{"new int[][]{{Integer.MIN_VALUE},{Integer.MIN_VALUE}}"}),
                fields("holds", RowIdentities.noDistinctEqualRows(new int[][]{{Integer.MIN_VALUE},{Integer.MIN_VALUE}})), fields());
        row(25, fields("entry", "MadeRows#reverse", "arguments", new String[]{"1", "2", "false"}),
                fields("holds", MadeRows.reverse(1, 2, false)), fields());
        row(26, fields("entry", "MadeRows#reverse", "arguments", new String[]{"0", "0", "true"}),
                fields("holds", MadeRows.reverse(0, 0, true)), fields());
        row(27, fields("entry", "MadeRows#iterator", "arguments", new String[]{"1", "2", "false"}),
                fields("holds", MadeRows.iterator(1, 2, false)), fields());
        row(28, fields("entry", "MadeRows#iterator", "arguments", new String[]{"0", "0", "true"}),
                fields("holds", MadeRows.iterator(0, 0, true)), fields());
        row(29, fields("entry", "MadeRows#alwaysDistinct", "arguments", new String[]{"1", "2", "false"}),
                fields("holds", MadeRows.alwaysDistinct(1, 2, false)), fields());
        row(30, fields("entry", "MadeRows#alwaysDistinct", "arguments", new String[]{"0", "0", "true"}),
                fields("holds", MadeRows.alwaysDistinct(0, 0, true)), fields());
        row(31, fields("entry", "MatrixRows#rectangular", "arguments", new String[]{"new long[][]{null}"}),
                fields("holds", MatrixRows.rectangular(new long[][]{null})), fields());
        row(32, fields("entry", "MatrixRows#rectangular", "arguments", new String[]{"new long[][]{{1L},{2L}}"}),
                fields("holds", MatrixRows.rectangular(new long[][]{{1L},{2L}})), fields());
        row(33, fields("entry", "MatrixRows#rectangular", "arguments", new String[]{"new long[][]{{1L},{}}"}),
                fields("holds", MatrixRows.rectangular(new long[][]{{1L},{}})), fields());
        row(34, fields("entry", "MatrixRows#singleShape", "arguments", new String[]{"new long[][]{null}"}),
                fields("holds", MatrixRows.singleShape(new long[][]{null})), fields());
        row(35, fields("entry", "MatrixRows#singleShape", "arguments", new String[]{"new long[][]{{1L},{2L}}"}),
                fields("holds", MatrixRows.singleShape(new long[][]{{1L},{2L}})), fields());
        row(36, fields("entry", "MatrixRows#singleShape", "arguments", new String[]{"new long[][]{{1L},{}}"}),
                fields("holds", MatrixRows.singleShape(new long[][]{{1L},{}})), fields());
        row(37, fields("entry", "MatrixRows#shape", "arguments", new String[]{"new long[][]{null}"}),
                fields("holds", MatrixRows.shape(new long[][]{null})), fields());
        row(38, fields("entry", "MatrixRows#shape", "arguments", new String[]{"new long[][]{{1L},{2L}}"}),
                fields("holds", MatrixRows.shape(new long[][]{{1L},{2L}})), fields());
        row(39, fields("entry", "MatrixRows#shape", "arguments", new String[]{"new long[][]{{1L},{}}"}),
                fields("holds", MatrixRows.shape(new long[][]{{1L},{}})), fields());
        row(40, fields("entry", "MatrixRows#same", "arguments", new String[]{"new long[][]{{1L},{2L}}"}),
                fields("holds", MatrixRows.same(new long[][]{{1L},{2L}})), fields());
        row(41, fields("entry", "MatrixRows#same", "arguments", new String[]{"new long[][]{{1L},{}}"}),
                fields("holds", MatrixRows.same(new long[][]{{1L},{}})), fields());
        row(42, fields("entry", "MatrixRows#noNull", "arguments", new String[]{"new long[][]{{1L},{2L}}"}),
                fields("holds", MatrixRows.noNull(new long[][]{{1L},{2L}})), fields());
        row(43, fields("entry", "MatrixRows#noNull", "arguments", new String[]{"new long[][]{null}"}),
                fields("holds", MatrixRows.noNull(new long[][]{null})), fields());
    }
}
