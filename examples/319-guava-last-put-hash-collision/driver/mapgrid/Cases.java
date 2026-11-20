package mapgrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;
import com.google.common.collect.ImmutableMap;
import java.util.*;

public final class Cases {
    private static final String[] KEYS = {"QED","R&D","X"};
    static void visit(String[] word, int code, int place) {
        ImmutableMap.Builder<String,Integer> b = ImmutableMap.builder();
        for (int i=0; i<word.length; i++) b.put(word[i],i+1);
        ImmutableMap<String,Integer> m = b.buildKeepingLast();
        List<Object[]> pairs = new ArrayList<>();
        for (var e : m.entrySet()) pairs.add(new Object[]{e.getKey(),e.getValue()});
        pairs.sort(Comparator.<Object[],String>comparing(x -> (String)x[0]).thenComparingInt(x -> (Integer)x[1]));
        int[] values = new int[3];
        for (int k=0;k<3;k++) { Integer v=m.get(KEYS[k]); values[k]=v==null?0:v; }
        Grid.row(code,fields("initial",new int[0],"keys",word),fields("size",m.size(),"lookup",values,"entries",pairs),
            fields("size",Projection.size(code),"lookup",Projection.lookup(code),"entries",Projection.entries(code)));
        if (word.length<4) for(int i=0;i<3;i++) {
            String[] child=Arrays.copyOf(word,word.length+1); child[word.length]=KEYS[i];
            visit(child,code+(i+1)*place,place*3);
        }
    }
    public static void main(String[] args) {
        if (KEYS[0].hashCode()!=KEYS[1].hashCode() || KEYS[0].equals(KEYS[1])) throw new AssertionError();
        visit(new String[0],0,1);
    }
}
