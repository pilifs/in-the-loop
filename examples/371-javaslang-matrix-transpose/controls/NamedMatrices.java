import javaslang.collection.List;

/** Four named original inputs, checked separately from the binary grid. */
public final class NamedMatrices {
    static String observed(List<List<Integer>> matrix) {
        try {
            return List.transpose(matrix).toString();
        } catch (IllegalArgumentException error) {
            return error.getClass().getName();
        }
    }

    public static void main(String[] args) {
        if (args.length != 1 || !(args[0].equals("parent") || args[0].equals("landed")))
            throw new IllegalArgumentException("select parent or landed");
        var singleEmpty = List.<Integer>empty();
        var inputs = List.of(List.of(List.of(1,2,3),List.of(4,5,6)), List.of(List.of(1,2),List.of(3)),
                List.of(singleEmpty,List.of(1)), List.of(singleEmpty,singleEmpty));
        String rejected = "java.lang.IllegalArgumentException";
        String[] expected = {"List(List(1, 4), List(2, 5), List(3, 6))",
                args[0].equals("parent") ? "List(List(1, 3), List(2))" : rejected,
                args[0].equals("parent") ? "List(List(1))" : rejected, "List()"};
        int row = 0;
        for (var matrix : inputs) {
            String result = observed(matrix);
            if (!result.equals(expected[row])) throw new AssertionError(matrix + " -> " + result);
            System.out.println(row++ + "\t" + matrix + "\t" + result);
        }
    }
}
