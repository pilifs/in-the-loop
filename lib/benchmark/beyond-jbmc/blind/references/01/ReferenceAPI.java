import java.util.ArrayList;
import java.util.Arrays;
import org.jruby.dirgra.DirectedGraph;
import org.jruby.dirgra.Vertex;
public final class ReferenceAPI {
    static final class Key implements org.jruby.dirgra.ExplicitVertexID {
        final int id;
        Key(int id){this.id=id;}
        public int getID(){return id;}
        public int hashCode(){return id;}
        public boolean equals(Object o){return o instanceof Key && ((Key)o).id==id;}
    }
    public static long primary(int n) {
        DirectedGraph<Key> g=new DirectedGraph<>();
        Key first=new Key(0),last=new Key(1);
        Vertex<Key> a=g.findOrCreateVertexFor(first), b=g.findOrCreateVertexFor(last);
        Key item=n==0?first:last;
        g.removeVertexFor(item);
        if (g.findVertexFor(item)!=null || g.size()!=1) return 0;
        Vertex<Key> fresh=g.findOrCreateVertexFor(item);
        return fresh!=(n==0?a:b) && g.findVertexFor(n==0?last:first)==(n==0?b:a)
            && new ArrayList<>(g.getInorderData()).equals(n==0?Arrays.asList(last,first):Arrays.asList(first,last)) ? 1:0;
    }
    public static long control(int n) {
        DirectedGraph<Key> g=new DirectedGraph<>();Key key=new Key(n);
        return g.findOrCreateVertexFor(key)==g.findOrCreateVertexFor(new Key(n)) && g.size()==1 ? 1:0;
    }
}
