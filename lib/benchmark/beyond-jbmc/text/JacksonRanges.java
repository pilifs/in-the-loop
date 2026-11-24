import com.fasterxml.jackson.core.io.NumberInput;

public final class JacksonRanges {
    static char[] digits(int suffix, int offset) {
        char[] a = new char[22];
        String prefix = "9223372036854775";
        a[0] = 'x'; a[21] = 'y';
        for (int i=0; i<16; ++i) a[offset+i]=prefix.charAt(i);
        a[offset+16]=(char)('0'+suffix/100);
        a[offset+17]=(char)('0'+suffix/10%10);
        a[offset+18]=(char)('0'+suffix%10);
        return a;
    }

    public static boolean arrayRange(int suffix, boolean negative, int offset) {
        if (suffix<0 || suffix>999 || offset<0 || offset>2) return true;
        char[] a=digits(suffix,offset);
        return NumberInput.inLongRange(a,offset,19,negative) == (suffix <= (negative ? 808 : 807));
    }

    public static boolean stringRange(int suffix, boolean negative) {
        if (suffix<0 || suffix>999) return true;
        String s=new String(digits(suffix,1),1,19);
        return NumberInput.inLongRange(s,negative) == (suffix <= (negative ? 808 : 807));
    }

    public static boolean accepted(int suffix, boolean negative, int offset) {
        if (suffix<0 || suffix>(negative ? 808 : 807) || offset<0 || offset>2) return true;
        char[] a=digits(suffix,offset);
        long magnitude=-9223372036854775000L-suffix;
        return NumberInput.inLongRange(a,offset,19,negative)
                && NumberInput.parseLong19(a,offset,negative)==(negative ? magnitude : -magnitude);
    }

    public static boolean allDigits(char[] text, int offset, boolean negative) {
        if (text == null || offset < 0 || offset > text.length-19) return true;
        long n=0, limit=negative ? Long.MIN_VALUE : -Long.MAX_VALUE;
        boolean fits=true;
        for (int i=0; i<19; ++i) {
            int d=text[offset+i]-'0';
            if (d<0 || d>9) return true;
            if (fits) {
                if (n<limit/10 || n*10<limit+d) fits=false;
                else n=n*10-d;
            }
        }
        return NumberInput.inLongRange(text,offset,19,negative)==fits
                && (!fits || NumberInput.parseLong19(text,offset,negative)==(negative ? n : -n));
    }
}
