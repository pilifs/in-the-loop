package durationgrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;
import org.apache.commons.lang3.time.DurationFormatUtils;

public final class Cases {
    public static void main(String[] args) {
        int code=0;
        for(int h=0;h<=12;h++)for(boolean pad:new boolean[]{false,true})for(String p:new String[]{"HxH","H'x'H","HH"}) {
            long ms=h*3600000L;
            String actual=DurationFormatUtils.formatDuration(ms,p,pad);
            boolean equal=DurationFormatUtils.formatDuration(ms,"HxH",pad).equals(DurationFormatUtils.formatDuration(ms,"H'x'H",pad));
            Grid.row(code,fields("hours",h,"pad",pad,"pattern",p),fields("text",actual,"quoting",equal),
                    fields("text",Projection.text(code),"quoting",Projection.quoting(code)));
            code++;
        }
    }
}
