import java.time.LocalDateTime;
import java.util.Locale;
import java.util.stream.Collectors;
import net.fortuna.ical4j.model.Recur;

public class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        Locale locale = Locale.forLanguageTag(args[0]);
        Locale.setDefault(locale);
        String rule = "FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU" + (args[1].equals("default") ? "" : ";WKST=" + args[1]);
        Recur<LocalDateTime> recur = new Recur<>(rule);
        LocalDateTime start = LocalDateTime.of(1997, 8, 5, 9, 0);
        String dates = recur.getDates(start, start, start.plusMonths(2)).stream().map(LocalDateTime::toString).collect(Collectors.joining(","));
        String repeated = recur.getDates(start, start, start.plusMonths(2)).stream().map(LocalDateTime::toString).collect(Collectors.joining(","));
        if (!dates.equals(repeated)) throw new AssertionError("repeat expansion differs");
        return Locale.getDefault().toLanguageTag() + "/" + rule + "/" + dates;
    }
}
