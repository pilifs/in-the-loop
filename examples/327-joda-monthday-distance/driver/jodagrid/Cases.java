package jodagrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;
import org.joda.time.*;
import org.joda.time.chrono.ISOChronology;

public final class Cases {
    static Object read(MonthDay a,MonthDay b) {
        try { return Days.daysBetween(a,b).getDays(); } catch(IllegalArgumentException ex) {return ex.getClass().getName();}
    }
    public static void main(String[] args) {
        String[] names={"02-27","02-28","02-29","03-01","03-02"};
        int code=0;
        for(String x:names)for(String y:names) {
            MonthDay a=new MonthDay(Integer.parseInt(x.substring(0,2)),Integer.parseInt(x.substring(3)),ISOChronology.getInstanceUTC());
            MonthDay b=new MonthDay(Integer.parseInt(y.substring(0,2)),Integer.parseInt(y.substring(3)),ISOChronology.getInstanceUTC());
            Object forward=read(a,b), reverse=read(b,a);
            boolean both=forward instanceof Integer && reverse instanceof Integer;
            Grid.row(code,fields("start",x,"end",y,"chronology","ISO-UTC"),
                fields("normal",forward instanceof Integer?null:forward,"days",forward instanceof Integer?forward:null,
                       "completion",both?"both":"excluded","reversal",both?(Integer)forward==-(Integer)reverse:null),
                fields("normal",Projection.normal(code),"days",Projection.days(code),"reversal",Projection.reversal(code)));
            code++;
        }
    }
}
