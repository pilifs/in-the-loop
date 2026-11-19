package claims;

public class EnumOrder {
    enum Unit { HOUR {}, DAY, YEAR {} }
    enum Other { DAY }

    @SuppressWarnings({"unchecked", "rawtypes"})
    public static boolean order(boolean pickHour) {
        Unit unit = pickHour ? Unit.HOUR : Unit.YEAR;
        if (unit.getDeclaringClass() != Unit.class || unit.compareTo(Unit.DAY) != (pickHour ? -1 : 1)
                || Unit.HOUR.compareTo(Unit.YEAR) != -2 || unit.compareTo(unit) != 0) return false;
        Comparable erased = unit;
        try { erased.compareTo(Other.DAY); return false; } catch (ClassCastException expected) {}
        try { erased.compareTo("hour"); return false; } catch (ClassCastException expected) {}
        try { erased.compareTo(null); return false; } catch (NullPointerException expected) {}
        return true;
    }

    public static void main(String[] args) {
        if (!order(true) || !order(false)) throw new AssertionError();
    }
}
