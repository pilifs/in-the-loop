import org.apache.commons.lang3.text.StrBuilder;

@SuppressWarnings("deprecation")
public final class ConstructorPhase {
    static class Sub extends StrBuilder {
        int phase = 7;
        int calls, observed;
        Sub(String source) { super(source); }
        @Override public StrBuilder append(String value) {
            calls++;
            observed = phase;
            return super.append(value);
        }
    }
    public static boolean history(String source) {
        Sub sub = new Sub(source);
        int length = source == null ? 0 : source.length();
        int calls = source == null ? 0 : 1;
        if (sub.calls != calls || sub.observed != 0 || sub.length() != length) return false;
        if (sub.append("B") != sub || sub.calls != calls + 1 || sub.observed != 7 || sub.length() != length + 1) return false;
        for (int i = 0; i < length; i++) if (sub.charAt(i) != source.charAt(i)) return false;
        return sub.charAt(length) == 'B';
    }
    public static boolean emptySkips() { return new Sub("").calls == 0; }
    public static boolean alreadyInitialized() { return new Sub("A").observed == 7; }
}
