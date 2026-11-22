package datawork;

import static datawork.RowMapper.*;

public final class RowChecks {
    public static int values(int code) {
        String[][] rows = input(code);
        return correct(rows, parseRows(rows)) ? 1 : 0;
    }

    public static int fresh(int code) {
        String[][] rows = input(code), originals = rows.clone(), contents = copyContents(rows);
        return isolated(rows, originals, contents, parseRows(rows), parseRows(rows)) ? 1 : 0;
    }
}
