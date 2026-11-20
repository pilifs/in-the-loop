package labelgrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class Cases {
    public static void main(String[] args) {
        int code=0;
        for(int n:new int[]{-1,0,10}) for(String s:new String[]{null,"","x"}) {
            Grid.row(code,new Object[]{n,s},fields("label",Label.label(n,s)),fields("label",Projection.label(code)));
            code++;
        }
    }
}
