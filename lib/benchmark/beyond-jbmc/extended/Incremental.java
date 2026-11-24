import org.apache.commons.codec.digest.MurmurHash3;
public final class Incremental {
    static boolean valid(byte[] a,int off,int len) {return a!=null && off>=0 && len>=0 && off<=a.length && len<=a.length-off;}
    public static boolean tail(byte[] a,int off,int len,int seed) {
        if (!valid(a,off,len)) return true;
        boolean high=false;
        for (int i=len-(len%4);i<len;++i) if (a[off+i]<0) high=true;
        return (MurmurHash3.hash32(a,off,len,seed)!=MurmurHash3.hash32x86(a,off,len,seed))==high;
    }
    public static boolean chunks(byte[] a,int off,int len,int split,int seed) {
        if (!valid(a,off,len) || split<0 || split>len) return true;
        byte[] original=a.clone();
        MurmurHash3.IncrementalHash32x86 h=new MurmurHash3.IncrementalHash32x86();
        h.start(seed);h.add(a,off,split);h.add(a,off+split,len-split);
        int expected=MurmurHash3.hash32x86(original,off,len,seed);
        if (h.end()!=expected || h.end()!=expected) return false;
        for (int i=0;i<a.length;++i) if (a[i]!=original[i]) return false;
        return true;
    }
    public static boolean resetThree(byte[] a,int first,int second,int seed) {
        if (a==null || first<0 || second<first || second>a.length) return true;
        MurmurHash3.IncrementalHash32x86 h=new MurmurHash3.IncrementalHash32x86();
        h.start(~seed);h.add(a,0,first);h.start(seed);
        h.add(a,0,first);h.add(a,first,second-first);h.add(a,second,a.length-second);
        int expected=MurmurHash3.hash32x86(a,0,a.length,seed);
        return h.end()==expected && h.end()==expected;
    }
}
