import com.fasterxml.jackson.core.*;

import java.math.*;

public class PublicCaller {
    static String large(boolean approximateFirst) throws Exception {
        String digits = "12345678901234567890123";
        try (var p = new JsonFactory().createParser(digits)) {
            p.nextToken();
            double approx = approximateFirst ? p.getDoubleValue() : 0;
            BigInteger exact = p.getBigIntegerValue();
            if (!approximateFirst) approx = p.getDoubleValue();
            return exact + ":" + (approx == new BigInteger(digits).doubleValue());
        }
    }

    public static String observe(String[] a) throws Exception {
        if (a[0].equals("challenge")) return large(true) + "/" + large(false);
        boolean ctrl = a[0].equals("control");
        try (var p = new JsonFactory().createParser(ctrl ? "[7]" : "[2.5,7.5]")) {
            p.nextToken();
            p.nextToken();
            if (ctrl)
                return p.getBigIntegerValue() + "/" + p.getDoubleValue() + "/" + p.nextToken();
            if (p.getDecimalValue().compareTo(new BigDecimal("2.5")) != 0)
                throw new AssertionError("first token value");
            p.nextToken();
            return p.getNumberType()
                    + "/"
                    + p.getBigIntegerValue()
                    + "/"
                    + p.getDecimalValue()
                    + "/"
                    + p.getDoubleValue();
        }
    }
}
