import org.pcollections.TreePVector;
import org.pcollections.PVector;

public final class PersistentVector {
    static boolean matches(PVector<Integer> v, int[] values) {
        if (v.size()!=values.length) return false;
        for (int k=0;k<values.length;++k) if (v.get(k).intValue()!=values[k]) return false;
        return true;
    }
    public static boolean branches(int n,int i,int replacement) {
        if (n<1 || n>6 || i<0 || i>=n) return true;
        PVector<Integer> base=TreePVector.empty();
        int[] ref=new int[n],changed=new int[n],removed=new int[n-1];
        for (int k=0;k<n;++k) {
            base=base.plus(10*k);ref[k]=10*k;changed[k]=k==i?replacement:10*k;
            if (k!=i) removed[k<i?k:k-1]=10*k;
        }
        PVector<Integer> a=base.with(i,replacement);
        if (!matches(base,ref) || !matches(a,changed)) return false;
        PVector<Integer> b=base.minus(i);
        if (!matches(base,ref) || !matches(a,changed) || !matches(b,removed)) return false;
        PVector<Integer> c=a.minus(i);
        return matches(base,ref) && matches(a,changed) && matches(b,removed) && matches(c,removed);
    }
}
