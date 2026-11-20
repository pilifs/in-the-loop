package zones;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.zone.ZoneRules;
import java.util.List;

public final class Offsets {
    public static List<ZoneOffset> offsets(ZoneId zone, LocalDateTime when) {
        ZoneRules rules = zone.getRules();
        return java.util.List.of(rules.getOffset(when));
    }
}
