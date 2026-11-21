public final class NullSlice {
    public static int observe(int offset, int count) {
        try { new String((char[]) null, offset, count); return 0; }
        catch (NullPointerException e) { return 1; }
        catch (StringIndexOutOfBoundsException e) { return 2; }
    }
    public static int order() { return observe(-1,1) * 100 + observe(0,-1) * 10 + observe(0,0); }
    public static void main(String[] args) { System.out.println(order()); }
}
