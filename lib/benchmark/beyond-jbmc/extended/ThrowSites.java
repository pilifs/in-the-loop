public final class ThrowSites {
    public static final class Reader {
        int[] data;
        public int read() {
            return data.length;
        }
    }
    public static int original(int mode) {
        Reader w=mode==0 ? null : new Reader();
        if (mode==2) w.data=new int[1];
        return w.read();
    }
    public static int repaired(int mode) {
        Reader w=new Reader();
        if (mode==2) w.data=new int[1];
        return w.read();
    }
    static int helper(Reader w) { return w.read(); }
    public static int withHelper(int mode) {
        Reader w=mode==0 ? null : new Reader();
        if (mode==2) w.data=new int[1];
        return helper(w);
    }
    static int inner(int mode,boolean replace,NullPointerException[] caught) {
        try { return withHelper(mode); }
        catch (NullPointerException e) {
            caught[0]=e;
            if (replace) throw new NullPointerException();
            throw e;
        }
    }
    public static boolean coarse(int mode) {
        if (mode<0 || mode>2) return true;
        try {return original(mode)==1 && mode==2;}
        catch (NullPointerException e) {return mode!=2;}
    }
    public static boolean history(int mode,boolean replace) {
        if (mode<0 || mode>2) return true;
        NullPointerException[] caught=new NullPointerException[1];
        try {return inner(mode,replace,caught)==1 && mode==2 && caught[0]==null;}
        catch (NullPointerException outer) {
            return mode!=2 && caught[0]!=null && (outer==caught[0])==!replace
                && outer.getClass()==NullPointerException.class && caught[0].getClass()==NullPointerException.class;
        }
    }
    public static void main(String[] args) {
        for (int mode=0;mode<=2;mode++) for(int variant=0;variant<=4;variant++) {
            NullPointerException[] caught=new NullPointerException[1];
            try {
                int value=variant==0?original(mode):variant==1?repaired(mode):variant==2?withHelper(mode):inner(mode,variant==4,caught);
                System.out.println(mode+" "+variant+" return "+value);
            } catch (NullPointerException e) {
                System.out.println(mode+" "+variant+" "+e.getClass().getName()+" "+e.getStackTrace()[0]+" caught "+
                    (caught[0]==null?"absent":caught[0].getStackTrace()[0])+" same "+(e==caught[0]));
            }
        }
    }
}
