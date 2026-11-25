import org.HdrHistogram.Histogram;

public class PublicCaller {
    static final long X = (1L << 62) - 1;

    static void record(Histogram target, long... values) {
        for (long value : values) target.recordValue(value);
    }

    static String compare(Histogram a, Histogram b) {
        try {
            return Boolean.toString(a.equals(b));
        } catch (RuntimeException e) {
            return e.getClass().getSimpleName();
        }
    }

    static String both(Histogram a, Histogram b) {
        return compare(a, b) + "/" + compare(b, a);
    }

    static String totals(Histogram a, Histogram b) {
        return a.getTotalCount() + "/" + b.getTotalCount();
    }

    static String counts(Histogram a, Histogram b, long at) {
        return a.getCountAtValue(at) + "/" + b.getCountAtValue(at);
    }

    static String extrema(Histogram h) {
        return h.getMinValue() + ":" + h.getMaxValue();
    }

    public static String observe(String[] args) {
        Histogram a = new Histogram(3);
        Histogram b = new Histogram(3);
        if (args[0].equals("order")) {
            record(a, 10, 20, 30);
            record(b, 30, 10, 20);
            String ordered = both(a, b);
            b.recordValue(20);
            return "ordered=" + ordered + " extra=" + both(a, b) + " totals=" + totals(a, b)
                    + " at20=" + counts(a, b, 20);
        }
        record(a, X, Long.MAX_VALUE);
        a.reset();
        switch (args[0]) {
        case "growth":
            a.recordValue(X);
            b.recordValue(X);
            return "totals=" + totals(a, b) + " atX=" + counts(a, b, X) + " equals=" + both(a, b);
        case "interior":
            record(a, 10, 20, 20, 40);
            record(b, 10, 30, 30, 40);
            return "totals=" + totals(a, b) + " extrema=" + extrema(a) + "/" + extrema(b)
                    + " at20=" + counts(a, b, 20) + " at30=" + counts(a, b, 30) + " equals=" + both(a, b);
        default:
            throw new IllegalArgumentException(args[0]);
        }
    }
}
