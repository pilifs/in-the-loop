package optionalgrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;
import java.util.*;

public final class Cases {
    public static void main(String[] args) {
        int code=0;
        for(Integer n:new Integer[]{null,0,1,2}) {
            Fallback f=new Fallback();
            int value=Choice.choose(Optional.ofNullable(n),f);
            String[] trace=new String[f.calls]; Arrays.fill(trace,"fallback");
            Grid.row(code,fields("present",n),fields("value",value,"callbacks",trace),
                    fields("value",Projection.value(code),"callbacks",Projection.callbacks(code)));
            code++;
        }
    }
}
