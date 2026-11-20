package paint;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class Cases {
    public static void main(String[] args) {
        for(int mask=0;mask<8;mask++) {
            Outcome out=Paint.run(mask);
            Throwable[] suppressed=out.primary==null?new Throwable[0]:out.primary.getSuppressed();
            String[] tags=new String[suppressed.length];
            for(int i=0;i<tags.length;i++)tags[i]=((Tagged)suppressed[i]).tag;
            Grid.row(mask,fields("left",(mask&1)!=0,"right",(mask&2)!=0,"body",(mask&4)!=0),
                    fields("primary",out.primary==null?null:out.primary.tag,"suppressed",tags,"close",java.util.Arrays.copyOf(out.trace,out.closed)),
                    fields("primary",Projection.primary(mask),"suppressed",Projection.suppressed(mask),"close",Projection.close(mask)));
        }
    }
}
