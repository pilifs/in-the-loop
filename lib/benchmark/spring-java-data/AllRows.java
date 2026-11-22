package datawork;

import static org.intheloop.controls.Grid.*;

/** Each row-identity partition occurs once. Distinct identities can receive equal words. */
public final class AllRows {
    public static void main(String[] args) {
        int id = 0;
        int[][] partitions = {{},{0},{0,0},{0,1},{0,0,0},{0,0,1},{0,1,0},{0,1,1},{0,1,2}};
        for (int[] partition : partitions) {
            int count = 0, variants = 1;
            for (int index : partition) if (index == count) { count++; variants *= 31; }
            for (int value = 0; value < variants; value++) {
                int[] ids = new int[count];
                String[][] pool = new String[count][];
                int encoded = value;
                for (int i = count-1; i >= 0; i--) {
                    ids[i] = encoded % 31;
                    pool[i] = RowMapper.word(ids[i]);
                    encoded /= 31;
                }
                String[][] rows = new String[partition.length][];
                for (int i = 0; i < rows.length; i++) rows[i] = pool[partition[i]];
                row(id++,fields("partition",partition,"words",ids),fields("values",RowMapper.parseRows(rows),
                        "aliases",Cases.aliases(rows),"fresh",Cases.identity(rows)),null);
            }
        }
    }
}
