import datawork.MatrixReferences;
import java.io.BufferedWriter;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.zip.GZIPOutputStream;
import javaslang.collection.List;

public final class MatrixReplay {
    // Label by reference. A non-null result outside the original palette is -1.
    private static String labels(List<? extends List<?>> matrix, Object[] refs) {
        var rows = new ArrayList<ArrayList<Integer>>();
        for (List<?> row : matrix) {
            var cells = new ArrayList<Integer>();
            for (Object cell : row) {
                int i = 0;
                while (i < refs.length && refs[i] != cell) i++;
                cells.add(i == refs.length ? -1 : i);
            }
            rows.add(cells);
        }
        return rows.toString();
    }

    // Deliberately wrong: swap the dimensions but keep the flat row-major order.
    // Applying it twice recovers the input even when the first matrix is wrong.
    private static List<List<Object>> reshape(List<List<Object>> matrix) {
        Object[] flat = new Object[6];
        int i = 0;
        for (List<Object> row : matrix) {
            for (Object cell : row) flat[i++] = cell;
        }
        return MatrixReferences.matrix(flat, matrix.head().length(), matrix.length());
    }

    private static String rectangle(int code, boolean wide) {
        Object[] refs = MatrixReferences.palette();
        int height = wide ? 2 : 3;
        var input = MatrixReferences.matrix(MatrixReferences.select(refs, code), height, 6 / height);
        String before = labels(input, refs);
        var once = List.transpose(input);
        var twice = List.transpose(once);
        var copies = once.map(row -> row.map(cell -> cell == null ? null : new MatrixReferences.Cell()));
        var reshaped = reshape(input);
        return String.join("\t", "rectangle", Integer.toString(code), Integer.toString(height),
                before, labels(once, refs), labels(twice, refs), labels(input, refs),
                Boolean.toString(once.equals(copies)), labels(copies, refs),
                labels(reshaped, refs), labels(reshape(reshaped), refs),
                Integer.toString(MatrixReferences.roundTrip(code, wide)));
    }

    private static String boundary(int shape, int choice) {
        Object[] refs = MatrixReferences.palette();
        var input = MatrixReferences.edgeInput(shape, refs[choice]);
        var once = List.transpose(input);
        var twice = List.transpose(once);
        return String.join("\t", "boundary", Integer.toString(shape), Integer.toString(choice),
                labels(input, refs), labels(once, refs), labels(twice, refs),
                Boolean.toString(once == input), Boolean.toString(twice == input),
                Integer.toString(MatrixReferences.boundaries(shape, choice)));
    }

    public static void main(String[] args) throws Exception {
        try (var out = new BufferedWriter(new OutputStreamWriter(
                new GZIPOutputStream(Files.newOutputStream(Path.of(args[1]))), StandardCharsets.UTF_8))) {
            for (String token : Files.readAllLines(Path.of(args[0]))) {
                int code = Integer.parseInt(token);
                for (boolean wide : new boolean[]{true, false}) {
                    out.write(rectangle(code, wide));
                    out.newLine();
                }
            }
            for (int shape = 0; shape < 5; shape++) {
                for (int choice = 0; choice < 8; choice++) {
                    out.write(boundary(shape, choice));
                    out.newLine();
                }
            }
        }
        LoadedClasses.main(java.util.Arrays.copyOfRange(args, 2, args.length));
    }
}
