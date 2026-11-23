import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) {
        int id=0;
        for (int n : new int[]{Integer.MIN_VALUE,-1,0,1,Integer.MAX_VALUE}) for (boolean shared : new boolean[]{false,true}) {
        Checkout.Pair p=Checkout.Pair.open(n,shared); int before=p.backup().remaining(); boolean taken=p.primary().take();
        row(id++,fields("n",n,"shared",shared),fields("same",p.primary()==p.backup(),"taken",taken,"before",before,"after",p.backup().remaining()),fields());
        }
    }
}
