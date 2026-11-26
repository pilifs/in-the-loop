import org.springframework.scheduling.support.*;

import java.time.*;
import java.util.*;

public class PublicCaller {
    public static String observe(String[] args) {
        boolean control = args[0].equals("june"), leap = args[0].equals("leap");
        Instant start = Instant.parse(leap ? "2096-02-29T00:00:00Z" : "2021-03-10T00:00:00Z");
        String expression = leap ? "0 0 0 29 2 *" : control ? "0 0 0 30 6 *" : "0 0 0 31 6 *";
        Date input = Date.from(start);
        CronTrigger trigger = new CronTrigger(expression, TimeZone.getTimeZone("UTC"));
        String result;
        try {
            Date next = trigger.nextExecutionTime(new SimpleTriggerContext(input, input, input));
            result = next == null ? "null" : next.toInstant().toString();
        } catch (IllegalArgumentException e) {
            result = e.getClass().getSimpleName();
        }
        try {
            CronExpression direct = CronExpression.parse(expression);
            if (control) {
                ZonedDateTime next = direct.next(start.atZone(ZoneOffset.UTC));
                if (!next.getZone().equals(ZoneOffset.UTC)
                        || !next.toInstant().toString().equals(result)) return result + "/" + next;
                return result;
            }
            return result + "/" + direct.next(LocalDateTime.ofInstant(start, ZoneOffset.UTC));
        } catch (NoClassDefFoundError unavailable) {
            return control ? result : result + "/absent";
        }
    }
}
