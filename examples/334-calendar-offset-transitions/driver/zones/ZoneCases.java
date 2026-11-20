package zones;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.zone.ZoneRulesProvider;
import java.util.List;
import java.util.TimeZone;
import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class ZoneCases {
    public static void main(String[] args) {
        System.err.println("tzdb " + ZoneRulesProvider.getVersions("America/Toronto").lastKey());
        int code = 0;
        for (String zone : new String[]{"UTC", "America/Toronto"}) {
            String[] times = {"2024-03-10T01:30","2024-03-10T02:30","2024-03-10T03:30",
                              "2024-11-03T00:30","2024-11-03T01:30","2024-11-03T02:30"};
            for (String time : times) {
                for (String defaultZone : new String[]{"UTC","Asia/Tokyo"}) {
                    TimeZone.setDefault(TimeZone.getTimeZone(defaultZone));
                    List<ZoneOffset> actual = Offsets.offsets(ZoneId.of(zone), LocalDateTime.parse(time));
                    int[] seconds = actual.stream().mapToInt(ZoneOffset::getTotalSeconds).toArray();
                    Grid.row(code, fields("zone",zone,"local",time,"default",defaultZone),
                            fields("count",actual.size(),"ordered",seconds),
                            fields("count",Appointment.count(code),"ordered",Appointment.ordered(code)));
                    code++;
                }
            }
        }
    }
}
