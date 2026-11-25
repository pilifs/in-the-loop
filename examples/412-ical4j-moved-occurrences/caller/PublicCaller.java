import java.io.StringReader;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.time.temporal.Temporal;
import java.time.temporal.TemporalQueries;
import java.util.*;
import net.fortuna.ical4j.data.CalendarBuilder;
import net.fortuna.ical4j.model.ComponentGroup;
import net.fortuna.ical4j.model.Period;
import net.fortuna.ical4j.model.Property;
import net.fortuna.ical4j.model.component.VEvent;
import net.fortuna.ical4j.model.property.Uid;

public class PublicCaller {
    static String event(String details) {
        return "BEGIN:VEVENT\nUID:series-a\nDTSTAMP:20210701T000000Z\n" + details + "\nEND:VEVENT\n";
    }
    static final String master = event("DTSTART:20210701T000000Z\nDTEND:20210701T003000Z\nRRULE:FREQ=DAILY");
    static final String moved = event("RECURRENCE-ID:20210715T000000Z\nDTSTART;VALUE=DATE:20210714\nDTEND;VALUE=DATE:20210715");
    static final String a = event("RECURRENCE-ID:20210715T000000Z\nDTSTART:20210716T000000Z\nDTEND:20210716T013000Z");
    static final String b = event("RECURRENCE-ID:20210716T000000Z\nDTSTART:20210716T030000Z\nDTEND:20210716T040000Z");
    static final DateTimeFormatter UTC = DateTimeFormatter.ofPattern("MM-dd'T'HH:mm'Z'").withZone(ZoneOffset.UTC);

    static String expand(String overrides, boolean midday) throws Exception {
        String ics = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//PublicCaller//EN\n" + master + overrides + "END:VCALENDAR\n";
        var calendar = new CalendarBuilder().build(new StringReader(ics.replace("\n", "\r\n")));
        var events = calendar.<VEvent>getComponents("VEVENT");
        var group = new ComponentGroup<>(events, new Uid("series-a"));
        String time = midday ? "T12:00:00Z" : "T00:00:00Z";
        var span = new Period<>(Instant.parse("2021-07-14" + time), Instant.parse("2021-07-16" + time));
        var rows = new ArrayList<String>();
        for (var p : group.calculateRecurrenceSet(span)) {
            Temporal start = p.getStart();
            String typed = start instanceof LocalDate date ? "DATE " + date.toString().substring(5)
                    : start instanceof Instant || ZoneOffset.UTC.equals(start.query(TemporalQueries.offset()))
                            ? "UTC " + UTC.format(Instant.from(start)) : start.getClass().getSimpleName() + " " + start;
            var owner = p.getComponent();
            String id = owner == null ? "no component" :
                    owner.<Property>getProperty("RECURRENCE-ID").map(Property::getValue).orElse("master");
            if (owner != null && events.stream().noneMatch(event -> event == owner)) id += " (detached component)";
            rows.add(typed + " " + p.getDuration() + " " + id);
        }
        Collections.sort(rows);
        return String.join("; ", rows);
    }
    public static String observe(String[] args) throws Exception {
        return switch (args[0]) {
            case "all-day" -> expand(moved, false);
            case "master" -> expand("", false);
            case "two-orders" -> "AB=" + expand(a + b, true) + " / BA=" + expand(b + a, true);
            default -> throw new IllegalArgumentException();
        };
    }
}
