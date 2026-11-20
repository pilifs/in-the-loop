package labelgrid;

public final class Projection {
    private static final String[] TABLE={"S-1/null", "S-1/", "S-1/x", "S0/null", "S0/", "S0/x", "S10/null", "S10/", "S10/x"};
    public static int label(int code) {
        int n=code/3==0?-1:code/3==1?0:10;
        String s=code%3==0?null:code%3==1?"":"x";
        return TABLE[code].equals(Label.label(n,s))?1:0;
    }
}
