import com.google.re2j.Pattern;
public final class ReferenceAPI {
    static String text(int n) {return new String(Character.toChars(n==0?'A':n==1?110781:0x1f642));}
    public static long primary(int n) {String s=text(n);return Pattern.matches("\\Q"+s+"\\E",s)?1:0;}
    public static long control(int n) {String s=text(n);return Pattern.matches(s,s) && !Pattern.matches(s,"z")?1:0;}
}
