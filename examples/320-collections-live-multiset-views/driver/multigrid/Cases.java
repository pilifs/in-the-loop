package multigrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;
import java.util.*;
import org.apache.commons.collections4.MultiSet;
import org.apache.commons.collections4.multiset.HashMultiSet;

public final class Cases {
    public static void main(String[] args) {
        int code=0;
        for(int a=1;a<=3;a++) for(int b=1;b<=3;b++) for(String view:new String[]{"unique","entry"}) {
            HashMultiSet<String> m=new HashMultiSet<>();
            for(int i=0;i<a;i++)m.add("A");
            for(int i=0;i<b;i++)m.add("B");
            Iterator<?> it=(view.equals("unique")?m.uniqueSet():m.entrySet()).iterator();
            Object next=it.next(); String removed=next instanceof String?(String)next:(String)((MultiSet.Entry<?>)next).getElement();
            it.remove();
            Object input=fields("A",a,"B",b,"view",view);
            Object direct=fields("removed",removed,"total",m.size(),"membership",new boolean[]{m.contains("A"),m.contains("B")},"otherCount",m.getCount(removed.equals("A")?"B":"A"));
            Object adapter=fields("total",Projection.total(code),"membership",Projection.membership(code),"otherCount",Projection.otherCount(code));
            Grid.row(code,input,direct,adapter);
            code++;
        }
    }
}
