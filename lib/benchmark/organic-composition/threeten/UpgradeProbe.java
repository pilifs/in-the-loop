import java.text.ParsePosition;
import java.util.Locale;
import org.threeten.bp.ZonedDateTime;
import org.threeten.bp.format.DateTimeFormatter;
import org.threeten.bp.format.DateTimeFormatterBuilder;
import org.threeten.bp.format.DateTimeParseException;
import org.threeten.bp.format.ResolverStyle;

public class UpgradeProbe {
    public static String observe(String[] args) {
        DateTimeFormatter formatter = new DateTimeFormatterBuilder()
            .append(DateTimeFormatter.ISO_ZONED_DATE_TIME).toFormatter(Locale.ROOT)
            .withResolverStyle(ResolverStyle.STRICT);
        ParsePosition cursor = new ParsePosition(0);
        String text = args[1] + args[2];
        StringBuilder history = new StringBuilder();
        for (int i = 0; i < 3; i++) {
            if (i > 0) history.append('|');
            try {
                ZonedDateTime parsed = ZonedDateTime.from(formatter.parse(text, cursor));
                if (!"cursor".equals(args[0])) history.append(parsed.toInstant());
            } catch (DateTimeParseException end) {
                history.append("end@").append(end.getErrorIndex());
            }
            history.append('/').append(cursor.getIndex()).append('/').append(cursor.getErrorIndex());
        }
        return history.toString();
    }

    public static boolean overlap(boolean berlin) {
        String first = berlin ? "2016-10-30T02:00+02:00[Europe/Berlin]" : "2016-11-06T01:00-04:00[America/New_York]";
        String later = berlin ? "2016-10-30T02:00+01:00[Europe/Berlin]" : "2016-11-06T01:00-05:00[America/New_York]";
        String history = observe(new String[]{"instant", first, later});
        return history.contains(berlin ? "2016-10-30T01:00:00Z" : "2016-11-06T06:00:00Z");
    }
}
