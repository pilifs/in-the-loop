import com.google.common.collect.Ordering;
import org.apache.commons.lang3.ObjectUtils;

public final class ExactOrder {
    private static int units(String a, String b) {
        int i = 0;
        while (i < a.length() && i < b.length()) {
            int difference = a.charAt(i) - b.charAt(i);
            if (difference != 0) return difference;
            i++;
        }
        return a.length() - b.length();
    }

    public static boolean commons(String a, String b) {
        return ObjectUtils.compare(a, b) == units(a, b);
    }

    public static boolean onlySign(String a, String b) {
        int difference = units(a, b);
        return ObjectUtils.compare(a, b) == (difference < 0 ? -1 : difference > 0 ? 1 : 0);
    }

    public static boolean guava(String a, String b) {
        return Ordering.natural().compare(a, b) == units(a, b);
    }

    public static boolean firstOnTie(String a, String b) {
        return Ordering.natural().min(a, b) == (units(a, b) <= 0 ? a : b);
    }

    public static boolean secondOnTie(String a, String b) {
        return Ordering.natural().min(a, b) == (units(a, b) < 0 ? a : b);
    }

    public static boolean sameReference(String a) {
        return ObjectUtils.compare(a, a) == 0 && Ordering.natural().min(a, a) == a;
    }

    public static boolean direct(String a, String b) {
        return a.compareTo(b) == units(a, b);
    }
}
