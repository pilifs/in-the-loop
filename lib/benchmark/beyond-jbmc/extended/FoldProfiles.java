import com.google.common.base.Ascii;
import org.apache.commons.lang3.StringUtils;
public final class FoldProfiles {
    public static boolean guavaString(char a,char b) {
        return Ascii.equalsIgnoreCase(String.valueOf(a),String.valueOf(b))==CaseFolding.ascii(a,b);
    }
    public static boolean guavaSequence(char a,char b) {
        return Ascii.equalsIgnoreCase(new CaseFolding.One(a),new CaseFolding.One(b))==CaseFolding.ascii(a,b);
    }
    public static boolean langString(char a,char b) {
        return StringUtils.equalsIgnoreCase(String.valueOf(a),String.valueOf(b))==CaseFolding.unicode(a,b);
    }
    public static boolean langSequence(char a,char b) {
        return StringUtils.equalsIgnoreCase(new CaseFolding.One(a),new CaseFolding.One(b))==CaseFolding.unicode(a,b);
    }
}
