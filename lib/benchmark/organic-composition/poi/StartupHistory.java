import java.text.DecimalFormatSymbols;
import java.util.Locale;
import org.apache.poi.ss.usermodel.DataFormatter;
import org.apache.poi.util.LocaleUtil;

/** Start in the declared JVM locale so that the first operation constructs the actual retained receiver. */
public class StartupHistory {
    public static String history(String mode, boolean kazakhFirst) {
        DataFormatter retained = new DataFormatter();
        Locale kazakh = Locale.forLanguageTag("kk-KZ");
        Locale initial = kazakhFirst ? kazakh : Locale.US;
        Locale other = kazakhFirst ? Locale.US : kazakh;
        boolean currency = mode.equals("custom");
        boolean date = mode.equals("date");
        String pattern = currency ? "#,##0.000000000\"тг.\"" : date ? "yyyy-mm-dd" : "0.0";
        int index = currency ? -1 : date ? 14 : 2;
        double amount = date ? 45292 : 0.001;
        StringBuilder out = new StringBuilder();
        try {
            for (Locale locale : new Locale[]{initial, other, initial}) {
                LocaleUtil.setUserLocale(locale);
                String first = retained.formatRawCellContents(amount, index, pattern);
                String repeat = retained.formatRawCellContents(amount, index, pattern);
                String peer = new DataFormatter().formatRawCellContents(amount, index, pattern);
                if (out.length() != 0) out.append('|');
                out.append(LocaleUtil.getUserLocale().toLanguageTag()).append('[')
                   .append(DecimalFormatSymbols.getInstance(locale).getDecimalSeparator()).append("]:")
                   .append(first).append('~').append(repeat).append('~').append(peer)
                   .append("~literal=").append(first.endsWith("тг."));
            }
            return out.toString();
        } finally {
            LocaleUtil.resetUserLocale();
        }
    }

    public static boolean currency(boolean kazakhFirst) {
        return history("custom", kazakhFirst).contains("тг.");
    }

    public static void main(String[] args) {
        System.out.println("ORIGINAL-VALUE " + history(args[0], args[1].equals("kk-KZ")));
    }
}
