import org.threeten.extra.OffsetDate;

import java.time.*;
import java.time.temporal.ChronoUnit;

public class PublicCaller {
    static long days(OffsetDate a, OffsetDate b) {
        return Duration.between(a.atTime(LocalTime.MIDNIGHT), b.atTime(LocalTime.MIDNIGHT))
                        .getSeconds()
                / 86400;
    }

    public static String observe(String[] args) {
        if (args[0].equals("challenge")) {
            var a = OffsetDate.MIN;
            var b = OffsetDate.MAX;
            long n = LocalDate.MAX.toEpochDay() - LocalDate.MIN.toEpochDay() + 1;
            long d = a.until(b, ChronoUnit.DAYS),
                    rd = b.until(a, ChronoUnit.DAYS),
                    w = a.until(b, ChronoUnit.WEEKS),
                    rw = b.until(a, ChronoUnit.WEEKS);
            return "days="
                    + (d == n && rd == -n)
                    + "/weeks="
                    + (w == n / 7 && rw == -n / 7)
                    + "/antisymmetric="
                    + (d == -rd && w == -rw);
        }
        var a = OffsetDate.of(LocalDate.of(2000, 1, 1), ZoneOffset.UTC);
        var b =
                args[0].equals("control")
                        ? OffsetDate.of(LocalDate.of(2000, 1, 3), ZoneOffset.UTC)
                        : OffsetDate.of(LocalDate.of(2000, 1, 1), ZoneOffset.ofHours(5));
        return a.until(b, ChronoUnit.DAYS)
                + "/"
                + b.until(a, ChronoUnit.DAYS)
                + ":oracle="
                + days(a, b)
                + "/"
                + days(b, a);
    }
}
