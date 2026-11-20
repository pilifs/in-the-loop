package bridgegrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class Cases {
    @SuppressWarnings({"rawtypes","unchecked"})
    public static void main(String[] args) {
        Object[] inputs={null,-1,0,1,"one"};
        for(int code=0;code<inputs.length;code++) {
            Object x=inputs[code], value=null; String failure=null;
            Plus erased=new Plus(); Mapper raw=erased;
            try { value=raw.map(x); } catch(ClassCastException e){failure=e.getClass().getName();}
            int typed=-1;
            if(code<4) { Plus m=new Plus(); typed=java.util.Objects.equals(m.map((Integer)x),value)&&m.entries==erased.entries?1:0; }
            Grid.row(code,fields("type",x==null?"null":x.getClass().getName(),"value",x),
                fields("value",value,"exception",failure,"entries",erased.entries,"typedAgreement",typed),
                fields("value",Projection.value(code),"exception",Projection.exception(code),"entries",Projection.entries(code),
                       "typedAgreement",Projection.typedAgreement(code)));
        }
    }
}
