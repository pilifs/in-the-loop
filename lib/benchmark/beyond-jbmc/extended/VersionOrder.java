import org.semver4j.Semver;
public final class VersionOrder {
    public static boolean pre(String digits) {
        if (digits==null || digits.length()==0 || digits.length()>20 || digits.length()>1 && digits.charAt(0)=='0') return true;
        for (int i=0;i<digits.length();++i) if (digits.charAt(i)<'0' || digits.charAt(i)>'9') return true;
        int expected=digits.length()>1 ? 1 : Integer.compare(digits.charAt(0),'1');
        try { return Integer.signum(new Semver("1.0.0-"+digits).compareTo(new Semver("1.0.0-1")))==expected; }
        catch (NumberFormatException oldOverflow) {return false;}
    }
    public static boolean overflow(String digits) {
        if (digits==null || digits.length()!=19 && digits.length()!=20 || digits.charAt(0)=='0') return true;
        for(int i=0;i<digits.length();++i) if (digits.charAt(i)<'0' || digits.charAt(i)>'9') return true;
        boolean exceeds=digits.length()>19 || digits.compareTo("9223372036854775807")>0;
        try {return new Semver("1.0.0-"+digits).compareTo(new Semver("1.0.0-1"))>0 && !exceeds;}
        catch(NumberFormatException e){return exceeds;}
    }
    public static boolean caret(int range,int v) {
        if (range<0 || range>3 || v<0 || v>3) return true;
        String[] ranges={"^0","^0.x","^0.0","^0.0.x"},versions={"0.0.0","0.0.5","0.5.0","1.0.0"};
        return new Semver(versions[v]).satisfies(ranges[range])==(range<2?v<3:v<2);
    }
}
