import com.google.common.primitives.Ints;

public final class HexClient {
    static final long MALFORMED = Long.MIN_VALUE, UNKNOWN = MALFORMED + 1, INVALID = MALFORMED + 2;
    static int ascii(char c) {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return -1;
    }
    static boolean positive(String s) { return s.length() == 8 && s.startsWith("7ffffff"); }
    static boolean negative(String s) { return s.length() == 9 && s.startsWith("-8000000"); }
    public static boolean nullReturns(String s) {
        if (!positive(s) && !negative(s)) return true;
        int d = ascii(s.charAt(s.length()-1));
        Integer result = Ints.tryParse(s,16);
        return (result == null) == (positive(s) ? d < 0 : d != 0);
    }
    public static boolean boxedValue(String s) {
        if (!positive(s) && !negative(s)) return true;
        int d = ascii(s.charAt(s.length()-1));
        Integer result = Ints.tryParse(s,16);
        if (positive(s) && d >= 0) return result != null && result.intValue() == 0x7ffffff0 + d;
        if (negative(s) && d == 0) return result != null && result.intValue() == Integer.MIN_VALUE;
        return result == null;
    }
    public static boolean rejectsMinimum(String s) {
        if (!negative(s)) return true;
        return Ints.tryParse(s,16) == null;
    }
    public static boolean directReached(String s) {
        if (!positive(s) && !negative(s)) return true;
        Ints.tryParse(s,16);
        return false;
    }
    public static long parse(String s) {
        if (s == null) return MALFORMED;
        int pos = s.indexOf('=');
        if (pos < 0 || s.lastIndexOf('=') != pos) return MALFORMED;
        if (!s.substring(0,pos).equals("id")) return UNKNOWN;
        Integer number = Ints.tryParse(s.substring(pos+1),16);
        return number == null ? INVALID : number.longValue();
    }
    // Streaming oracle. No substring, String search or library numeric parser.
    static long scan(String s) {
        if (s == null) return MALFORMED;
        int pos=-1,count=0; boolean sign=false,bad=false;
        long value=0;
        for (int i=0;i<s.length();i++) {
            char unit=s.charAt(i);
            if (unit=='=') { if (pos!=-1) return MALFORMED; pos=i; }
            else if (pos!=-1) {
                if (i==pos+1 && unit=='-') sign=true;
                else {
                    int d=ascii(unit); count++;
                    if (d<0 || value>0x80000000L/16) bad=true;
                    else { value=value*16+d; if (value>(sign?0x80000000L:0x7fffffffL)) bad=true; }
                }
            }
        }
        if (pos<0) return MALFORMED;
        if (pos!=2 || s.charAt(0)!='i' || s.charAt(1)!='d') return UNKNOWN;
        return bad || count==0 ? INVALID : sign ? -value : value;
    }
    static boolean inLanguage(String s) {
        if (s==null) return true;
        if (s.length()>6) return false;
        for (int i=0;i<s.length();i++) {
            char c=s.charAt(i);
            if (c!='i' && c!='d' && c!='=' && c!='0' && c!='F' && c!='-' && c!='\ud800') return false;
        }
        return true;
    }
    public static boolean composition(String s) { return !inLanguage(s) || parse(s)==scan(s); }
    public static boolean earlyKey(String s) {
        if (s==null || !inLanguage(s)) return true;
        int p=s.indexOf('=');
        long value=p>=0 && !s.substring(0,p).equals("id") ? UNKNOWN : parse(s);
        return value==scan(s);
    }
    public static boolean dropSign(String s) {
        if (s==null || !inLanguage(s)) return true;
        long value=s.startsWith("id=-") ? parse("id="+s.substring(4)) : parse(s);
        return value==scan(s);
    }
    public static boolean nullShape() { return parse(null)==MALFORMED; }
}
