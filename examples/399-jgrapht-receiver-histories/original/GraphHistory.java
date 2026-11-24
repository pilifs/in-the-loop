import org.jgrapht.graph.DefaultEdge;
import org.jgrapht.graph.DirectedAcyclicGraph;

public final class GraphHistory {
    public static boolean identities(int selection) {
        DirectedAcyclicGraph<String, DefaultEdge> graph = new DirectedAcyclicGraph<>(null, null, false);
        String a = "a", b = "b", c = "c";
        graph.addVertex(a);
        graph.addVertex(b);
        graph.addVertex(c);
        DefaultEdge old = new DefaultEdge();
        if (!graph.addEdge(a, b, old)) return false;
        try {
            switch (selection) {
                case 0:
                    if (graph.addEdge("x", b, old)) return false;
                    break;
                case 1:
                    graph.addEdge("x", b, new DefaultEdge());
                    return false;
                case 2:
                    graph.addEdge(a, c, null);
                    return false;
                default: throw new IllegalArgumentException("selection");
            }
        } catch (RuntimeException e) {
            if (selection == 1 && e.getClass() != IllegalArgumentException.class) return false;
            if (selection == 2 && e.getClass() != NullPointerException.class) return false;
            if (selection == 0) return false;
        }
        return graph.vertexSet().size() == 3 && graph.containsVertex(a) && graph.containsVertex(b)
            && graph.containsVertex(c) && graph.edgeSet().size() == 1 && graph.getEdge(a, b) == old
            && graph.getEdgeSource(old) == a && graph.getEdgeTarget(old) == b;
    }
}
