import org.apache.arrow.memory.*;
import org.apache.arrow.vector.*;
import org.apache.arrow.vector.util.DecimalUtility;
import org.apache.arrow.vector.validate.ValidateUtil.ValidateException;

import java.math.BigDecimal;
import java.util.*;

public class PublicCaller {
    static BaseFixedWidthVector allocate(BufferAllocator a, int width) {
        BaseFixedWidthVector v =
                width == 128 ? new DecimalVector("n", a, 5, 2) : new Decimal256Vector("w", a, 5, 2);
        v.allocateNew(2);
        return v;
    }

    static String check(BaseFixedWidthVector v) {
        try {
            v.validateScalars();
            return "ok";
        } catch (ValidateException e) {
            return e.getClass().getSimpleName();
        }
    }

    static void raw(BaseFixedWidthVector v, int width, int i, String value) {
        DecimalUtility.writeBigDecimalToArrowBuf(
                new BigDecimal(value), v.getDataBuffer(), i, width / 8);
        v.setIndexDefined(i);
    }

    static String values(BaseFixedWidthVector v) {
        return check(v) + "/" + List.of(v.getObject(0), v.getObject(1));
    }

    static String trial(BufferAllocator a, int width, String mode) {
        try (var v = allocate(a, width)) {
            if (mode.equals("control")) {
                raw(v, width, 0, "99.99");
                v.setValueCount(1);
                String valid = check(v);
                try (var invalid = allocate(a, width)) {
                    raw(invalid, width, 0, "1000.00");
                    invalid.setValueCount(1);
                    return valid + "/" + check(invalid);
                }
            }
            raw(v, width, 0, "999.99");
            raw(v, width, 1, "-999.99");
            v.setValueCount(2);
            return values(v);
        }
    }

    public static String observe(String[] a) {
        try (var alloc = new RootAllocator()) {
            if (a[0].equals("challenge"))
                try (var first = (DecimalVector) allocate(alloc, 128);
                        var second = (Decimal256Vector) allocate(alloc, 256)) {
                    first.setSafe(0, new BigDecimal("-999.99"));
                    first.setSafe(1, new BigDecimal("999.99"));
                    first.setValueCount(2);
                    for (int i = 0; i < 2; i++) second.setSafe(i, first.getObject(i));
                    second.setValueCount(2);
                    return values(first) + " / " + values(second);
                }
            return trial(alloc, 128, a[0]) + " / " + trial(alloc, 256, a[0]);
        }
    }
}
