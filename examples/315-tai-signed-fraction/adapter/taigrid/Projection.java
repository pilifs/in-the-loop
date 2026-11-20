package taigrid;

import org.threeten.extra.scale.TaiInstant;

public final class Projection {
    public static int nanos(int code) {
        switch (code % 4) {
            case 0: return 0;
            case 1: return 1;
            case 2: return 500000000;
            default: return 999999999;
        }
    }

    public static String text(int code) {
        switch (code) {
            case 0: return "-2.000000000s(TAI)";
            case 1: return "-1.999999999s(TAI)";
            case 2: return "-1.500000000s(TAI)";
            case 3: return "-1.000000001s(TAI)";
            case 4: return "-1.000000000s(TAI)";
            case 5: return "-0.999999999s(TAI)";
            case 6: return "-0.500000000s(TAI)";
            case 7: return "-0.000000001s(TAI)";
            case 8: return "0.000000000s(TAI)";
            case 9: return "0.000000001s(TAI)";
            case 10: return "0.500000000s(TAI)";
            case 11: return "0.999999999s(TAI)";
            case 12: return "1.000000000s(TAI)";
            case 13: return "1.000000001s(TAI)";
            case 14: return "1.500000000s(TAI)";
            case 15: return "1.999999999s(TAI)";
            case 16: return "2.000000000s(TAI)";
            case 17: return "2.000000001s(TAI)";
            case 18: return "2.500000000s(TAI)";
            case 19: return "2.999999999s(TAI)";
            default: throw new IllegalArgumentException();
        }
    }

    private static TaiInstant object(int code) {
        return TaiInstant.ofTaiSeconds(code / 4 - 2, nanos(code));
    }

    private static int agrees(TaiInstant actual, int code) {
        return actual.getTaiSeconds() == code / 4 - 2 && actual.getNano() == nanos(code) ? 1 : 0;
    }

    public static int format(int code) { return text(code).equals(object(code).toString()) ? 1 : 0; }
    public static int parse(int code) { return agrees(TaiInstant.parse(text(code)), code); }
    public static int roundTrip(int code) { return agrees(TaiInstant.parse(object(code).toString()), code); }
}
