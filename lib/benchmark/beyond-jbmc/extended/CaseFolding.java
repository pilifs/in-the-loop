import com.google.common.base.Ascii;
import org.apache.commons.lang3.StringUtils;

public final class CaseFolding {
    static final class One implements CharSequence {
        final char c;
        One(char c) { this.c=c; }
        public int length() { return 1; }
        public char charAt(int n) { if (n!=0) throw new IndexOutOfBoundsException(); return c; }
        public CharSequence subSequence(int i,int j) { return String.valueOf(c).subSequence(i,j); }
    }
    static boolean ascii(char a,char b) {
        int lo=a|32;
        return a==b || lo>='a' && lo<='z' && lo==(b|32);
    }
    static boolean unicode(char a,char b) {
        char u=Character.toUpperCase(a), v=Character.toUpperCase(b);
        return a==b || u==v || Character.toLowerCase(u)==Character.toLowerCase(v);
    }
    public static boolean strings(char a,char b) { return check(String.valueOf(a),String.valueOf(b),a,b); }
    public static boolean sequences(char a,char b) { return check(new One(a),new One(b),a,b); }
    static boolean check(CharSequence x,CharSequence y,char a,char b) {
        boolean g=Ascii.equalsIgnoreCase(x,y),l=StringUtils.equalsIgnoreCase(x,y);
        return g==ascii(a,b) && l==unicode(a,b) && g==Ascii.equalsIgnoreCase(y,x) && l==StringUtils.equalsIgnoreCase(y,x);
    }
    public static boolean same(char a,char b) {
        return Ascii.equalsIgnoreCase(String.valueOf(a),String.valueOf(b))==StringUtils.equalsIgnoreCase(String.valueOf(a),String.valueOf(b));
    }
    public static boolean nulls() {
        boolean throwsBoth=false,throwsLeft=false,throwsRight=false;
        try { Ascii.equalsIgnoreCase(null,null); } catch (NullPointerException e) { throwsBoth=true; }
        try { Ascii.equalsIgnoreCase(null,"a"); } catch (NullPointerException e) { throwsLeft=true; }
        try { Ascii.equalsIgnoreCase("a",null); } catch (NullPointerException e) { throwsRight=true; }
        return throwsBoth && throwsLeft && throwsRight
            && StringUtils.equalsIgnoreCase(null,null) && !StringUtils.equalsIgnoreCase(null,"a") && !StringUtils.equalsIgnoreCase("a",null);
    }
}
