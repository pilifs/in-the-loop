package bridgegrid;

public final class Plus implements Mapper<Integer> {
    public int entries;
    public Integer map(Integer n) {
        entries++;
        if (n==null) return 99;
        if (n==0) return 2;
        return n+1;
    }
}
