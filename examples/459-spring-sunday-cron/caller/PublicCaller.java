import java.time.LocalDateTime;
import org.springframework.scheduling.support.CronExpression;

public class PublicCaller {
    static LocalDateTime next(String days, LocalDateTime seed) {
        return CronExpression.parse("0 0 0 * * " + days).next(seed);
    }

    public static String observe(String[] args) {
        LocalDateTime start = LocalDateTime.of(2021, 2, 25, 15, 0);
        LocalDateTime sunday = next("SUN", start);
        return switch (args[0]) {
            case "first" -> next("SUN-SUN", start).toString();
            case "sunday" -> sunday + " " + next("0-0", start);
            case "next" -> next("SUN-SUN", sunday) + " " + next("7-7", sunday) + " " + next("SUN", sunday);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
