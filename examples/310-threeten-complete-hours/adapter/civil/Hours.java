package civil;

import org.threeten.bp.LocalDateTime;
import org.threeten.bp.temporal.ChronoUnit;

/** Each tick is one quarter hour since 2012-06-15 00:00 on the local civil clock. */
public final class Hours {
    private static LocalDateTime date(int tick) {
        return LocalDateTime.of(2012, 6, 15 + tick / 96, (tick % 96) / 4, 15 * (tick % 4));
    }

    public static long completeHours(int startTick, int endTick) {
        return date(startTick).until(date(endTick), ChronoUnit.HOURS);
    }
}
