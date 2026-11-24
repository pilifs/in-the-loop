import org.semver4j.Semver;

public final class Coercion {
    static String group(int v,boolean pad){return (pad?"0":"")+Integer.toString(v);}
    static boolean profile(int major,int minor,int patch,int parts,int mask,boolean first) {
        if (major<0 || major>19 || minor<0 || minor>19 || patch<0 || patch>19 || parts<1 || parts>3 || mask<0 || mask>7) return true;
        String input=group(major,(mask&1)!=0);
        if (parts>1) input+="."+group(minor,(mask&2)!=0);
        if (parts>2) input+="."+group(patch,(mask&4)!=0);
        Semver v=Semver.coerce(input);
        boolean padded=(mask & ((1<<parts)-1))!=0;
        if (first && padded) return v==null;
        String expected=major+"."+(parts>1?minor:0)+"."+(parts>2?patch:0);
        return v!=null && v.toString().equals(expected);
    }
    public static boolean oldGrammar(int major,int minor,int patch,int parts,int mask){return profile(major,minor,patch,parts,mask,true);}
    public static boolean newGrammar(int major,int minor,int patch,int parts,int mask){return profile(major,minor,patch,parts,mask,false);}
    public static boolean plain(){return Semver.coerce("plain")==null;}
}
