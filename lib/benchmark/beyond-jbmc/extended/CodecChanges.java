public final class CodecChanges {
    static boolean valid(byte[] b,int off,int len) {return b!=null && off>=0 && len>=0 && off<=b.length && len<=b.length-off;}
    static boolean equal(long[] a,long[] b) {return a.length==2 && b.length==2 && a[0]==b[0] && a[1]==b[1];}
    public static boolean seedBoundary(byte[] text,int off,int len,int seed) {
        if (!valid(text,off,len)) return true;
        return equal(before.CodecPublic.historic(text,off,len,seed),CodecPublic.historic(text,off,len,seed))==(seed>=0);
    }
    public static boolean historicalIdentity(byte[] text,int off,int len,int seed) {
        return !valid(text,off,len) || equal(before.CodecPublic.historic(text,off,len,seed),CodecPublic.historic(text,off,len,seed));
    }
    public static boolean unchanged32(byte[] text,int off,int len,int seed) {
        return !valid(text,off,len) || before.CodecPublic.hash32(text,off,len,seed)==CodecPublic.hash32(text,off,len,seed);
    }
}
