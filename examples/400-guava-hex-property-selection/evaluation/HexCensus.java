public final class HexCensus {
    static final char[] ALPHABET={'i','d','=','0','F','-','\ud800'};
    static final long[] counts=new long[4];
    static void strings(String s) {
        long r=HexClient.parse(s);
        if(r!=HexClient.scan(s)) throw new AssertionError("client disagrees with scanner");
        counts[r==HexClient.MALFORMED?0:r==HexClient.UNKNOWN?1:r==HexClient.INVALID?2:3]++;
        if(s.length()<6) for(char c:ALPHABET) strings(s+c);
    }
    public static void main(String[] args) {
        int falseMinimum=0;
        for(int i=0;i<=65535;i++) {
            String p="7ffffff"+(char)i,n="-8000000"+(char)i;
            if(!HexClient.nullReturns(p)||!HexClient.nullReturns(n)||!HexClient.boxedValue(p)||!HexClient.boxedValue(n))throw new AssertionError(i);
            if(!HexClient.rejectsMinimum(n)){if(i!='0')throw new AssertionError(i);falseMinimum++;}
        }
        strings("");
        if(falseMinimum!=1 || !java.util.Arrays.equals(counts,new long[]{83136,53862,208,51}) || !HexClient.nullShape()
            || HexClient.earlyKey("d==F") || HexClient.dropSign("id=-F"))throw new AssertionError();
        System.out.println("direct 131072 minimum-failures "+falseMinimum+" composition "+java.util.Arrays.toString(counts)+" null malformed");
        for(String s:new String[]{"id=7fffffff","id=80000000","id=-80000000","id=-80000001"}) {
            long value=HexClient.parse(s); if(value!=HexClient.scan(s))throw new AssertionError(s);
            System.out.println(s+" "+value);
        }
    }
}
