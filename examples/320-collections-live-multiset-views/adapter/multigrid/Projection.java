package multigrid;

import java.util.Iterator;
import org.apache.commons.collections4.MultiSet;
import org.apache.commons.collections4.multiset.AbstractMapMultiSet;
import org.apache.commons.collections4.multiset.HashMultiSet;

public final class Projection {
    private static int check(int code,int field) {
        int a=1+code/6, b=1+(code/2)%3;
        AbstractMapMultiSet<String> m=new HashMultiSet<>();
        m.add("A",a); m.add("B",b);
        String selected;
        if (code%2==0) { Iterator<String> i=m.uniqueSet().iterator(); selected=i.next(); i.remove(); }
        else { Iterator<MultiSet.Entry<String>> i=m.entrySet().iterator(); selected=i.next().getElement(); i.remove(); }
        boolean removedA="A".equals(selected);
        if (!removedA && !"B".equals(selected)) return 0;
        String other=removedA?"B":"A";
        if (field==0) return m.size()==(removedA?b:a)?1:0;
        if (field==1) return !m.contains(selected) && m.contains(other)?1:0;
        return m.getCount(other)==(removedA?b:a)?1:0;
    }
    public static int total(int code){return check(code,0);}
    public static int membership(int code){return check(code,1);}
    public static int otherCount(int code){return check(code,2);}
}
