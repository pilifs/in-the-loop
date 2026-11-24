import com.fasterxml.jackson.core.io.NumberInput;
public final class JacksonControl {
    public static boolean signBlind(int suffix) {
        if (suffix<0 || suffix>999) return true;
        char[] a=JacksonRanges.digits(suffix,1);
        return NumberInput.inLongRange(a,1,19,false)==NumberInput.inLongRange(a,1,19,true);
    }
    public static boolean all19Safe() {
        return NumberInput.inLongRange("9223372036854775808",false);
    }
}
