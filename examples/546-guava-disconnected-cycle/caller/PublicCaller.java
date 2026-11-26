import com.google.common.graph.*;

public class PublicCaller {
    public static String observe(String[] a) {
        MutableGraph<Integer> g = GraphBuilder.undirected().build();
        g.putEdge(1, 2);
        g.putEdge(2, 3);
        g.putEdge(3, 1);
        if (a[0].equals("challenge")) {
            g.removeEdge(3, 1);
            g.putEdge(3, 1);
            boolean triangle = Graphs.hasCycle(g);
            g.addNode(4);
            g.putEdge(5, 6);
            return triangle + "/" + Graphs.hasCycle(g);
        }
        g.addNode(4);
        if (a[0].equals("control")) g.removeEdge(3, 1);
        return Boolean.toString(Graphs.hasCycle(g));
    }
}
