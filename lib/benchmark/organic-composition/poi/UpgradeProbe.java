import java.text.DecimalFormatSymbols;
import java.util.Locale;
import java.util.TimeZone;
import org.apache.poi.ss.usermodel.DataFormatter;
import org.apache.poi.util.LocaleUtil;

public class UpgradeProbe {
    public static String observe(String[] args) {
        Locale initial = Locale.forLanguageTag(args[1]);
        Locale other = initial.equals(Locale.US) ? Locale.forLanguageTag("kk-KZ") : Locale.US;
        Locale previous = Locale.getDefault();
        try {
            Locale.setDefault(initial);
            LocaleUtil.setUserLocale(initial);
            LocaleUtil.setUserTimeZone(TimeZone.getTimeZone("UTC"));
            DataFormatter retained = new DataFormatter();
            boolean custom = args[0].equals("custom");
            boolean calendar = args[0].equals("date");
            String pattern = custom ? "#,##0.000000000\"тг.\"" : calendar ? "yyyy-mm-dd" : "0.0";
            double value = calendar ? 45292 : 0.001;
            int format = custom ? -1 : calendar ? 14 : 2;
            StringBuilder history = new StringBuilder();
            for (Locale locale : new Locale[] { initial, other, initial }) {
                LocaleUtil.setUserLocale(locale);
                String first = retained.formatRawCellContents(value, format, pattern);
                String repeat = retained.formatRawCellContents(value, format, pattern);
                String peer = new DataFormatter().formatRawCellContents(value, format, pattern);
                if (history.length() != 0) history.append('|');
                history.append(LocaleUtil.getUserLocale().toLanguageTag()).append('[')
                       .append(DecimalFormatSymbols.getInstance(locale).getDecimalSeparator()).append("]:")
                       .append(first).append('~').append(repeat).append('~').append(peer)
                       .append("~literal=").append(first.endsWith("тг."));
            }
            return history.toString();
        } finally {
            LocaleUtil.resetUserLocale();
            LocaleUtil.resetUserTimeZone();
            Locale.setDefault(previous);
        }
    }

    public static boolean currency(boolean kazakhFirst) {
        return observe(new String[]{"custom", kazakhFirst ? "kk-KZ" : "en-US"}).contains("тг.");
    }
}
