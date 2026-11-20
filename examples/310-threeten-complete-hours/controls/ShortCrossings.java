import org.threeten.bp.LocalDateTime;
import org.threeten.bp.temporal.ChronoUnit;

/** Enumerate every sub-hour crossing by comparing the dates of independently constructed endpoints. */
class ShortCrossings {
    public static void main(String[] args) {
        LocalDateTime midnight = LocalDateTime.of(2012, 6, 15, 0, 0);
        for (int start = 0; start < 192; start++) {
            LocalDateTime from = midnight.plusMinutes(start * 15L);
            for (int end = 0; end < 192; end++) {
                LocalDateTime to = midnight.plusMinutes(end * 15L);
                if (!to.toLocalDate().equals(from.toLocalDate()) && Math.abs((end - start) * 15) < 60) {
                    System.out.printf("%d %d %d%n", start, end, from.until(to, ChronoUnit.HOURS));
                }
            }
        }
    }
}
