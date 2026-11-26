import java.time.*;
import org.springframework.scheduling.support.CronExpression;

public class PublicCaller {
    static String stamp(ZonedDateTime z) {
        return z.toLocalDateTime().toString()+z.getOffset()+"="+z.toInstant();
    }
    public static String observe(String[] args) {
        boolean ny=args[0].equals("newyork");
        ZoneId zone=ZoneId.of(ny ? "America/New_York" : "Africa/Cairo");
        LocalDateTime start=LocalDateTime.parse(ny ? "2026-03-08T01:00" : args[0].equals("ordinary") ? "2025-04-23T22:00" : "2025-04-24T22:00");
        LocalDateTime gap=LocalDateTime.parse(ny ? "2026-03-08T02:00" : "2025-04-25T00:00");
        if(!zone.getRules().getValidOffsets(gap).isEmpty()) throw new IllegalStateException("time-zone data missing gap");
        var cron=CronExpression.parse(ny ? "0 0 0,2 * * ?" : "0 0 */2 * * ?");
        var first=cron.next(start.atZone(zone));
        return stamp(first)+" / "+stamp(cron.next(first));
    }
}
