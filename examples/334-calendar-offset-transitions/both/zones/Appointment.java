package zones;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.List;
import java.util.TimeZone;

public final class Appointment {
    static List<ZoneOffset> read(int code) {
        int pos = (code / 2) % 6;
        TimeZone.setDefault(TimeZone.getTimeZone((code & 1) == 0 ? "UTC" : "Asia/Tokyo"));
        ZoneId zone = ZoneId.of(code / 12 == 0 ? "UTC" : "America/Toronto");
        LocalDateTime local = pos < 3 ? LocalDateTime.of(2024, 3, 10, pos + 1, 30)
                : LocalDateTime.of(2024, 11, 3, pos - 3, 30);
        return Offsets.offsets(zone, local);
    }

    public static int count(int code) { return read(code).size(); }
    public static int ordered(int code) {
        List<ZoneOffset> offsets = read(code);
        int tag = 1;
        for (ZoneOffset offset : offsets) {
            int sec = offset.getTotalSeconds();
            int part = sec == 0 ? 1 : sec == -14400 ? 2 : sec == -18000 ? 3 : 0;
            if (part == 0) return -1;
            tag = tag * 4 + part;
        }
        return switch (tag) { case 1 -> 0; case 5 -> 1; case 6 -> 2; case 7 -> 3; case 27 -> 4; default -> -1; };
    }
}
