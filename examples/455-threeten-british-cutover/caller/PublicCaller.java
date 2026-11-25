import java.time.DateTimeException;
import java.time.LocalDate;
import java.time.chrono.ChronoLocalDate;
import java.time.chrono.ChronoPeriod;
import java.time.chrono.Chronology;
import java.util.Locale;
import org.threeten.extra.chrono.BritishCutoverChronology;
import org.threeten.extra.chrono.BritishCutoverDate;
import org.threeten.extra.chrono.JulianChronology;
import org.threeten.extra.chrono.JulianDate;
import org.threeten.extra.chrono.JulianEra;
import static java.time.temporal.ChronoField.DAY_OF_MONTH;
import static java.time.temporal.ChronoField.MONTH_OF_YEAR;
import static java.time.temporal.ChronoField.YEAR;
import static java.time.temporal.ChronoUnit.DAYS;
import static java.time.temporal.ChronoUnit.MONTHS;
import static java.time.temporal.ChronoUnit.YEARS;

public class PublicCaller {
    static String fields(ChronoLocalDate date) {
        return String.format(Locale.ROOT, "%04d-%02d-%02d", date.get(YEAR), date.get(MONTH_OF_YEAR),
                date.get(DAY_OF_MONTH));
    }

    static String julianDay(JulianDate date, int day) {
        try {
            return fields(date.with(DAY_OF_MONTH, day));
        } catch (DateTimeException e) {
            return e.getClass().getSimpleName();
        }
    }

    static String year(Chronology chronology, int input) {
        try {
            return Integer.toString(chronology.prolepticYear(JulianEra.BC, input));
        } catch (DateTimeException e) {
            return e.getClass().getSimpleName();
        }
    }

    static String limits(Chronology chronology) {
        return year(chronology, Integer.MIN_VALUE) + "/" + year(chronology, Integer.MAX_VALUE);
    }

    public static String observe(String[] args) {
        switch (args[0]) {
        case "month-year":
            return "month=" + fields(BritishCutoverDate.of(1752, 8, 12).plus(1, MONTHS))
                    + " year=" + fields(BritishCutoverDate.of(1751, 9, 12).plus(1, YEARS));
        case "day":
            BritishCutoverDate start = BritishCutoverDate.of(1752, 9, 2);
            BritishCutoverDate next = start.plus(1, DAYS);
            return "forward=" + fields(next) + " delta=" + (next.toEpochDay() - start.toEpochDay())
                    + " back=" + fields(next.minus(1, DAYS)) + " select12=" + fields(start.with(DAY_OF_MONTH, 12));
        case "period":
            BritishCutoverDate march = BritishCutoverDate.of(1753, 3, 18);
            BritishCutoverDate end = BritishCutoverDate.of(1752, 9, 1);
            ChronoPeriod period = march.until(end);
            ChronoLocalDate back = march.plus(period);
            return "period=" + period.get(YEARS) + "," + period.get(MONTHS) + "," + period.get(DAYS)
                    + " back=" + fields(back) + " epoch=" + back.toEpochDay() + " end=" + end.toEpochDay()
                    + " iso=" + LocalDate.of(1752, 9, 12).toEpochDay();
        case "julian-day":
            JulianDate february = JulianDate.of(2011, 2, 26);
            return "at30=" + julianDay(february, 30) + " at32=" + julianDay(february, 32);
        case "era":
            return "julian=" + limits(JulianChronology.INSTANCE) + " british=" + limits(BritishCutoverChronology.INSTANCE);
        default:
            throw new IllegalArgumentException(args[0]);
        }
    }
}
