import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) {
        int[][] inputs={{0,0},{0,3},{1,2},{2,0},{3,0}};
        for (int i=0;i<inputs.length;i++) {int m=inputs[i][0],v=inputs[i][1]; String outcome;
        try { outcome="return "+SafetySites.run(m,v); } catch (RuntimeException e) { outcome=e.getClass().getName(); }
        row(i,fields("mode",m,"value",v),fields("outcome",outcome),fields());
        }
    }
}
