package copy;

import java.util.Arrays;
import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class CopyCases {
    private static final Object[] ALPHABET = {null, "A", Integer.valueOf(1)};

    private static void visit(Object[] input, int id, int place) {
        String[] destination = new String[input.length];
        Arrays.fill(destination, "x");
        String exception = null;
        try {
            Copy.transfer(input, destination);
        } catch (ArrayStoreException problem) {
            exception = problem.getClass().getName();
        }
        Grid.row(id, fields("sourceType", input.getClass().getName(), "destinationType", destination.getClass().getName(),
                        "source", input), fields("exception", exception, "state", destination),
                fields("exception", Projection.thrown(id), "state", Projection.state(id)));
        if (input.length < 3) {
            for (int i = 0; i < ALPHABET.length; i++) {
                Object[] child = Arrays.copyOf(input, input.length + 1);
                child[input.length] = ALPHABET[i];
                visit(child, id + place * (i + 1), place * 3);
            }
        }
    }

    public static void main(String[] args) { visit(new Object[0], 0, 1); }
}
