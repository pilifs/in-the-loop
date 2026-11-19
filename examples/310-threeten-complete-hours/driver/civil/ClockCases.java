package civil;

import org.threeten.bp.LocalDateTime;
import org.threeten.bp.temporal.ChronoUnit;

public final class ClockCases {
    public static void main(String[] args) {
        LocalDateTime midnight = LocalDateTime.of(2012, 6, 15, 0, 0);
        LocalDateTime[] direct = new LocalDateTime[192];
        for (int i = 0; i < direct.length; i++) direct[i] = midnight.plusMinutes(15L * i);
        for (int i = 0; i < direct.length; i++) {
            int correspondence = 0, clock = 0, sameDay = 0, reverse = 0;
            for (int j = 0; j < direct.length; j++) {
                long hours = direct[i].until(direct[j], ChronoUnit.HOURS);
                long adapted = Hours.completeHours(i, j);
                if (hours != adapted) correspondence++;
                if (hours != ((15L * j - 15L * i) / 60)) {
                    clock++;
                    if (i / 96 == j / 96) sameDay++;
                }
                if (hours != -direct[j].until(direct[i], ChronoUnit.HOURS)) reverse++;
            }
            System.out.printf("{\"startTick\":%d,\"ends\":%d,\"correspondence\":%d,\"clock\":%d,\"sameDay\":%d,\"reverse\":%d}%n",
                              i, direct.length, correspondence, clock, sameDay, reverse);
        }
        System.out.printf("{\"forward\":%d,\"backward\":%d}%n", Hours.completeHours(94, 97), Hours.completeHours(97, 94));
    }
}
