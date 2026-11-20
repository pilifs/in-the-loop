package tiling;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class Cases {
    public static void main(String[] args) {
        for(int n=0;n<=18;n++) {
            Grid.row(n, fields("n",n), fields("exact",Floor.exact(n),"parity",Floor.parity(n)), fields());
        }
    }
}
