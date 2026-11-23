import org.jgrapht.graph.DirectedAcyclicGraph;

public final class GraphSink {
    public static Object captured;

    public static boolean capture(DirectedAcyclicGraph<?, ?> graph) {
        captured = graph;
        return graph != null;
    }
}
