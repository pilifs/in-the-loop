package datawork;

import java.math.BigDecimal;
import org.apache.commons.lang3.math.NumberUtils;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static Object observe(String text) {
        try {
            Number n = NumberUtils.createNumber(text);
            if (n instanceof BigDecimal d) return new Object[]{"BigDecimal", d.unscaledValue().toString(), d.scale()};
            if (n instanceof Float f) return new Object[]{"Float", Float.floatToRawIntBits(f)};
            if (n instanceof Double d) return new Object[]{"Double", Double.doubleToRawLongBits(d)};
            return new Object[]{n.getClass().getSimpleName(), n.longValue()};
        } catch (NumberFormatException error) { return error.getClass().getName(); }
    }

    public static void main(String[] args) {
        for (int i = 0; i < 3; i++)
            row(i,new String[]{Decimals.exact(i), Decimals.control(i), "1eE"},
                fields("precise",observe(Decimals.exact(i)), "preserved",new Object[]{observe(Decimals.control(i)),observe("1eE")}),
                fields("precise",Decimals.precise(i),"preserved",Decimals.preserved(i)));
    }
}
