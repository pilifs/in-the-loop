package paint;

public final class Projection {
    public static int primary(int code) {
        Outcome out=Paint.run(code);
        String want=(code&4)!=0?"B":(code&2)!=0?"R":(code&1)!=0?"L":null;
        return out.primary==null?(want==null?1:0):(out.primary.tag.equals(want)?1:0);
    }
    public static int suppressed(int code) {
        Outcome out=Paint.run(code);
        int count=0;
        if((code&4)!=0 && (code&2)!=0) count++;
        if((code&1)!=0 && (code&6)!=0) count++;
        if(out.primary==null)return count==0?1:0;
        Throwable[] failures=out.primary.getSuppressed();
        if(failures.length!=count)return 0;
        for(int i=0;i<count;i++) {
            String want=(i==0 && (code&6)==6)?"R":"L";
            if(!(failures[i] instanceof Tagged) || !((Tagged)failures[i]).tag.equals(want))return 0;
        }
        return 1;
    }
    public static int close(int code) {
        Outcome out=Paint.run(code);
        return out.closed==2 && "R".equals(out.trace[0]) && "L".equals(out.trace[1])?1:0;
    }
}
