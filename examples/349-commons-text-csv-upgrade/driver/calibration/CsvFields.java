package calibration;

import java.util.Arrays;
import org.apache.commons.text.StringEscapeUtils;

/** Print every input and the observed UTF-16 units, including CR, LF and quotes. */
public final class CsvFields {
    private static final char[] ALPHABET = {'a', ',', '"', '\r', '\n'};

    private static void observe(String field) {
        String outcome;
        try {
            String returned = StringEscapeUtils.escapeCsv(field);
            outcome = "\"returned\":" + (returned == null ? "null" : units(returned));
        } catch (Throwable thrown) {
            outcome = "\"threw\":\"" + thrown.getClass().getName() + "\"";
        }
        System.out.println("{\"input\":" + units(field) + "," + outcome + "}");
    }

    private static String units(String text) {
        return Arrays.toString(text.chars().toArray());
    }

    private static void visit(String prefix, int remaining) {
        if (remaining == 0) {
            observe(prefix);
            return;
        }
        for (char unit : ALPHABET) {
            visit(prefix + unit, remaining - 1);
        }
    }

    public static void main(String[] args) {
        for (int length = 0; length <= 3; length++) {
            visit("", length);
        }
    }
}
