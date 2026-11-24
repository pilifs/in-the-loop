public final class ExceptionAssertions {
    public static int original(int mode) {return ThrowSites.original(mode);}
    public static int repaired(int mode) {return ThrowSites.repaired(mode);}
    public static int helper(int mode) {return ThrowSites.withHelper(mode);}
    public static void returned(int mode) {
        if (mode<0 || mode>2) return;
        try {int result=ThrowSites.original(mode);if(mode==2 && result==1) assert false;}
        catch (NullPointerException e) {assert mode!=2;}
    }
}
