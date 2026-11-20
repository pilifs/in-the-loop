package maxgrid;

import java.util.Arrays;
import java.util.HexFormat;
import org.apache.commons.lang3.math.NumberUtils;
import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class MaxCases {
    private static String bits(double d) { return HexFormat.of().toHexDigits(Double.doubleToRawLongBits(d)); }

    private static void visit(double[] prefix, int key, int place) {
        int digit = 0;
        for (double value : new double[]{-1.0, -0.0, +0.0, 1.0}) {
            double[] array = Arrays.copyOf(prefix, prefix.length + 1);
            array[prefix.length] = value;
            int next = key + ++digit * place;
            int code = next - 1;
            double actual = NumberUtils.max(array);
            String[] input = new String[array.length];
            for (int i = 0; i < input.length; i++) input[i] = bits(array[i]);
            Grid.row(code, input, fields("numeric", bits(actual == 0.0 ? 0.0 : actual), "rawBits", bits(actual)),
                    fields("numeric", Projection.numeric(code), "rawBits", Projection.bits(code)));
            if (array.length < 3) visit(array, next, place * 4);
        }
    }

    public static void main(String[] args) { visit(new double[0], 0, 1); }
}
