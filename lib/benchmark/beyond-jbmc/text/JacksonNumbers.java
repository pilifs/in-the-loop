import com.fasterxml.jackson.core.io.NumberInput;

public final class JacksonNumbers {
    // A bijection from [0,11110] to the disclosed strings of length 0..4.
    public static String input(int ordinal) {
        int length=0, count=1;
        while (ordinal>=count) { ordinal-=count; count*=10; ++length; }
        char[] units=new char[length];
        String abc="079+-.eEx\u0661";
        for(int i=length-1;i>=0;--i) {units[i]=abc.charAt(ordinal%10);ordinal/=10;}
        return new String(units);
    }

    public static boolean trailing(String s) {
        int n=s.length();
        if (n<2 || s.charAt(n-1)!='.') return false;
        int first=(s.charAt(0)=='+' || s.charAt(0)=='-') ? 1 : 0;
        if (first==n-1) return false;
        for(int i=first;i<n-1;++i) if (s.charAt(i)<'0' || s.charAt(i)>'9') return false;
        return true;
    }

    public static boolean looks(String s) { return NumberInput.looksLikeValidNumber(s); }
}
