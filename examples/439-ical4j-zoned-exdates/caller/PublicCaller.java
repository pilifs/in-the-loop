import java.time.*;
import java.time.temporal.Temporal;
import java.util.ArrayList;
import net.fortuna.ical4j.model.Period;
import net.fortuna.ical4j.model.component.VEvent;
import net.fortuna.ical4j.model.property.ExDate;
import net.fortuna.ical4j.model.property.RRule;
import net.fortuna.ical4j.model.property.Uid;

public class PublicCaller {
    static String read(boolean spring, String exception) {
        LocalDate from = LocalDate.parse(spring ? "2024-03-30" : "2024-01-01");
        var start = from.atTime(9,0).atZone(ZoneId.of("Europe/Paris"));
        var event = new VEvent(start, Duration.ofHours(1), "Daily");
        event.add(new Uid("calendar-test"));
        event.add(new RRule<Temporal>("FREQ=DAILY;COUNT=3"));
        event.add(new ExDate<Temporal>(exception));
        var interval = new Period<>(from.atStartOfDay().toInstant(ZoneOffset.UTC),
                from.plusDays(3).atStartOfDay().toInstant(ZoneOffset.UTC));
        var periods = new ArrayList<String>();
        for (var p : event.calculateRecurrenceSet(interval)) {
            periods.add(Instant.from(p.getStart()) + "/" + Instant.from(p.getEnd()));
        }
        periods.sort(null);
        return periods.toString();
    }
    public static String observe(String[] args) {
        if (args[0].equals("spring")) return read(true,"20240331T070000Z") + " | " + read(true,"20240331T080000Z");
        return read(false,args[0].equals("end") ? "20240102T090000Z" : "20240102T080000Z");
    }
}
