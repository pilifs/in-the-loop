import java.util.HashSet;

public final class TrainingStock {
    public static TrainingStock captured;
    public static boolean capture(TrainingStock c) { captured=c;return c!=null; }
    private final HashSet<Object> depots=new HashSet<>(), receipts=new HashSet<>();
    public boolean addDepot(Object depot) {return depots.add(depot);}
    public boolean addReceipt(Object src,Object dst,Object id) {return depots.contains(src)&&depots.contains(dst)&&receipts.add(id);}
}
