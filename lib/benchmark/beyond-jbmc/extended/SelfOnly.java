import org.apache.commons.lang3.mutable.MutableObject;
public final class SelfOnly {
    @SuppressWarnings("unchecked")
    public static boolean terminates(int topology,int start) {
        if (topology<0 || topology>=64 || start < -1 || start>2) return true;
        MutableObject<Object>[] n=new MutableObject[]{new MutableObject<>(),new MutableObject<>(),new MutableObject<>()};
        for(int i=0;i<3;++i) {int dest=(topology >>> (2*i) & 3)-1;n[i].setValue(dest<0?null:n[dest]);}
        MutableObject<?> cursor=start<0?null:n[start];
        for(int i=0;i<=3;i++) {
            if (cursor==null || cursor.getValue()==cursor) return true;
            cursor=(MutableObject<?>)cursor.getValue();
        }
        return false;
    }
}
