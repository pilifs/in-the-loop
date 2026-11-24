import org.apache.commons.lang3.ArrayUtils;
import org.apache.commons.lang3.mutable.MutableInt;
import org.apache.commons.lang3.mutable.MutableObject;

public final class HeapTopology {
    public static final class Cell { public MutableInt payload; }
    static Cell cell(MutableInt value) { Cell c=new Cell(); c.payload=value; return c; }
    public static boolean entry(Cell[] cells) {
        if (cells==null || cells.length==0 || cells[0]==null || cells[0].payload==null) return true;
        MutableInt m=cells[0].payload;
        int value=m.intValue();
        return m.getAndAdd(1)==value && cells[0].payload.intValue()==value+1;
    }
    public static boolean constructed(int value,int mode) {
        if (mode<0 || mode>2) return true;
        MutableInt a=mode==0 ? null : new MutableInt(value);
        Cell[] c={cell(a),cell(mode==2 ? a : new MutableInt(value))};
        if (mode==0) {
            try { c[0].payload.getAndAdd(1); return false; }
            catch (NullPointerException expected) { return c[1].payload.intValue()==value; }
        }
        return entry(c) && c[1].payload.intValue()==(mode==2?value+1:value) && (c[1].payload==a)==(mode==2);
    }
    public static boolean unchanged(int value) {
        Cell[] c={cell(new MutableInt(value))}; c[0].payload.getAndAdd(1);
        return c[0].payload.intValue()==value;
    }
    static int index(Object[] n,Object x) {
        for (int i=0;i<n.length;++i) if (n[i]==x) return i;
        return -1;
    }
    @SuppressWarnings("unchecked")
    public static boolean walk(int topology,int start) {
        if (topology<0 || topology>=64 || start < -1 || start>2) return true;
        MutableObject<Object>[] n=new MutableObject[]{new MutableObject<>(),new MutableObject<>(),new MutableObject<>()};
        for (int i=0;i<3;++i) {
            int dst=(topology >>> (2*i) & 3)-1;
            n[i].setValue(dst<0?null:n[dst]);
        }
        Object[] visited=new Object[3];
        Object p=start<0?null:n[start]; int cursor=start, mask=0,k=0;
        while (p!=null && index(visited,p)<0) {
            if (k==3 || cursor<0 || (mask & (1<<cursor))!=0 || index(n,p)!=cursor) return false;
            visited[k++]=p; mask|=1<<cursor;
            p=((MutableObject<?>)p).getValue(); cursor=(topology >>> (2*cursor) & 3)-1;
        }
        return index(n,p)==cursor && (p==null || (mask & (1<<cursor))!=0);
    }
    public static boolean twoRoots(int value,boolean shared) {
        MutableInt a=new MutableInt(value),b=shared?a:new MutableInt(value);
        MutableObject<MutableInt> left=new MutableObject<>(), right=new MutableObject<>(), sibling=new MutableObject<>();
        left.setValue(a); right.setValue(b); sibling.setValue(new MutableInt(100));
        if (!left.getValue().equals(right.getValue()) || (left.getValue()==right.getValue())!=shared) return false;
        left.getValue().increment();
        return left.getValue().intValue()==value+1 && right.getValue().intValue()==(shared?value+1:value)
            && sibling.getValue().intValue()==100 && (left.getValue()==right.getValue())==shared;
    }
    public static boolean planes(boolean shared,char x,char y) {
        char[][] p={{x}},q=shared?p:new char[][]{{y}};
        char[][][] data={p,q};
        ArrayUtils.reverse((Object[])data);
        return data[0]==q && data[1]==p && p[0][0]==x && q[0][0]==(shared?x:y);
    }
}
