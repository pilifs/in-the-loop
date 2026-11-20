package seats;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class Cases {
    public static void main(String[] args) {
        int code = 0;
        for (int r = 1; r <= 3; r++) for (int c = 1; c <= 2; c++) {
            for (int y = 0; y < r; y++) for (int x = 0; x < c; x++) {
                int[][] a = Seats.mark(r,c,y,x);
                int[] shape = new int[a.length + 1], aliases = new int[a.length];
                shape[0] = a.length;
                for (int i = 0; i < a.length; i++) {
                    shape[i + 1] = a[i].length;
                    int j = 0;
                    while (a[i] != a[j]) j++;
                    aliases[i] = j;
                }
                Grid.row(code, new int[]{r,c,y,x}, fields("shape",shape,"cells",a,"identity",aliases),
                        fields("shape",Projection.shape(code),"cells",Projection.cells(code),"identity",Projection.identity(code)));
                code++;
            }
        }
    }
}
