import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "categories", "arguments", new String[]{"null"}),
                fields("holds", ReferenceCells.categories(null)), fields());
        row(1, fields("entry", "categories", "arguments", new String[]{"new ReferenceCells.Item[0]"}),
                fields("holds", ReferenceCells.categories(new ReferenceCells.Item[0])), fields());
        row(2, fields("entry", "categories", "arguments", new String[]{"new ReferenceCells.Item[1]"}),
                fields("holds", ReferenceCells.categories(new ReferenceCells.Item[1])), fields());
        row(3, fields("entry", "categories", "arguments", new String[]{"new ReferenceCells.Item[]{new ReferenceCells.Item()}"}),
                fields("holds", ReferenceCells.categories(new ReferenceCells.Item[]{new ReferenceCells.Item()})), fields());
        row(4, fields("entry", "noNullCell", "arguments", new String[]{"null"}),
                fields("holds", ReferenceCells.noNullCell(null)), fields());
        row(5, fields("entry", "noNullCell", "arguments", new String[]{"new ReferenceCells.Item[0]"}),
                fields("holds", ReferenceCells.noNullCell(new ReferenceCells.Item[0])), fields());
        row(6, fields("entry", "noNullCell", "arguments", new String[]{"new ReferenceCells.Item[1]"}),
                fields("holds", ReferenceCells.noNullCell(new ReferenceCells.Item[1])), fields());
        row(7, fields("entry", "noItemCell", "arguments", new String[]{"null"}),
                fields("holds", ReferenceCells.noItemCell(null)), fields());
        row(8, fields("entry", "noItemCell", "arguments", new String[]{"new ReferenceCells.Item[0]"}),
                fields("holds", ReferenceCells.noItemCell(new ReferenceCells.Item[0])), fields());
        row(9, fields("entry", "noItemCell", "arguments", new String[]{"new ReferenceCells.Item[1]"}),
                fields("holds", ReferenceCells.noItemCell(new ReferenceCells.Item[1])), fields());
        row(10, fields("entry", "noItemCell", "arguments", new String[]{"new ReferenceCells.Item[]{new ReferenceCells.Item()}"}),
                fields("holds", ReferenceCells.noItemCell(new ReferenceCells.Item[]{new ReferenceCells.Item()})), fields());
        row(11, fields("entry", "followsAlias", "arguments", new String[]{"true", "3"}),
                fields("holds", ReferenceCells.followsAlias(true, 3)), fields());
        row(12, fields("entry", "followsAlias", "arguments", new String[]{"false", "3"}),
                fields("holds", ReferenceCells.followsAlias(false, 3)), fields());
        row(13, fields("entry", "followsAlias", "arguments", new String[]{"true", "Integer.MAX_VALUE"}),
                fields("holds", ReferenceCells.followsAlias(true, Integer.MAX_VALUE)), fields());
        row(14, fields("entry", "alwaysShares", "arguments", new String[]{"true"}),
                fields("holds", ReferenceCells.alwaysShares(true)), fields());
        row(15, fields("entry", "alwaysShares", "arguments", new String[]{"false"}),
                fields("holds", ReferenceCells.alwaysShares(false)), fields());
    }
}
