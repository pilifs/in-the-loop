package paint;

public final class Projection {
    public static int primary(int mask) {
        Outcome out=Paint.run(mask);
        String want=(mask&4)!=0?"B":(mask&2)!=0?"R":(mask&1)!=0?"L":null;
        return out.primary==null?(want==null?1:0):(out.primary.tag.equals(want)?1:0);
    }
    public static int suppressed(int mask) {
        Outcome out=Paint.run(mask);
        int count=0;
        if((mask&4)!=0 && (mask&2)!=0) count++;
        if((mask&1)!=0 && (mask&6)!=0) count++;
        if(out.primary==null)return count==0?1:0;
        Throwable[] failures=out.primary.getSuppressed();
        if(failures.length!=count)return 0;
        for(int i=0;i<count;i++) {
            String want=(i==0 && (mask&6)==6)?"R":"L";
            if(!(failures[i] instanceof Tagged) || !((Tagged)failures[i]).tag.equals(want))return 0;
        }
        return 1;
    }
    public static int close(int mask) {
        Outcome out=Paint.run(mask);
        return out.closed==2 && "R".equals(out.trace[0]) && "L".equals(out.trace[1])?1:0;
    }
}
