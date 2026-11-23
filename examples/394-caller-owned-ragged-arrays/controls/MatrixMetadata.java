import org.apache.commons.math3.exception.DimensionMismatchException;
import org.apache.commons.math3.util.MathArrays;

public final class MatrixMetadata {
    public static boolean widths(long[][] matrix, boolean swap) {
        if (matrix == null || matrix.length != 2 || matrix[0] == null || matrix[1] == null) return true;
        int first = matrix[0].length, second = matrix[1].length;
        try {
            MathArrays.checkRectangular(matrix);
            return first == second;
        } catch (DimensionMismatchException mismatch) {
            int expected = mismatch.getDimension(), actual = mismatch.getArgument().intValue();
            return first != second && expected == (swap ? second : first) && actual == (swap ? first : second);
        }
    }

    public static boolean correct(long[][] matrix) { return widths(matrix, false); }
    public static boolean swapped(long[][] matrix) { return widths(matrix, true); }

    public static void main(String[] args) {
        int different = 0;
        for (int first = -1; first <= 2; first++) {
            for (int second = -1; second <= 2; second++) {
                long[][] rows = {first < 0 ? null : new long[first], second < 0 ? null : new long[second]};
                boolean mismatch = first >= 0 && second >= 0 && first != second;
                if (!correct(rows) || swapped(rows) == mismatch) throw new AssertionError(first + "," + second);
                if (mismatch) different++;
            }
        }
        if (different != 6) throw new AssertionError(different);
        System.out.println("16 two-row shapes; all 6 mismatches distinguish actual and expected widths");
    }
}
