package taigrid;

import java.util.Locale;
import org.intheloop.controls.Grid;
import org.threeten.extra.scale.TaiInstant;
import static org.intheloop.controls.Grid.fields;

public final class TaiCases {
    private static long[] fieldsOf(TaiInstant instant) {
        return new long[]{instant.getTaiSeconds(), instant.getNano()};
    }

    public static void main(String[] args) {
        int code = 0;
        for (int s = -2; s <= 2; s++) {
            for (int n : new int[]{0, 1, 500000000, 999999999}) {
                long total = s * 1000000000L + n;
                long absolute = Math.abs(total);
                String canonical = String.format(Locale.ROOT, "%s%d.%09ds(TAI)", total < 0 ? "-" : "",
                        absolute / 1000000000L, absolute % 1000000000L);
                TaiInstant object = TaiInstant.ofTaiSeconds(s, n);
                String formatted = object.toString();
                Grid.row(code, fields("seconds", s, "nanos", n, "canonical", canonical),
                        fields("format", formatted, "parse", fieldsOf(TaiInstant.parse(canonical)),
                               "roundTrip", fieldsOf(TaiInstant.parse(formatted))),
                        fields("format", Projection.format(code), "parse", Projection.parse(code),
                               "roundTrip", Projection.roundTrip(code)));
                code++;
            }
        }
    }
}
