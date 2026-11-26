import org.jgrapht.Graph;
import org.jgrapht.alg.connectivity.ConnectivityInspector;
import org.jgrapht.graph.*;

import java.util.*;

public class PublicCaller {
    static String run(String mode, boolean directed) {
        Graph<String, DefaultEdge> base =
                directed
                        ? new DefaultDirectedGraph<>(DefaultEdge.class)
                        : new SimpleGraph<>(DefaultEdge.class);
        var graph = new DefaultListenableGraph<>(base);
        if (!mode.equals("intent")) {
            for (String k : List.of("a", "b", "c")) graph.addVertex(k);
            graph.addEdge("a", "b");
        }
        var inspector = new ConnectivityInspector<>(graph);
        graph.addGraphListener(inspector);
        if (mode.equals("intent")) {
            graph.addVertex("a");
            graph.addVertex("b");
            graph.addEdge("a", "b");
            return new TreeSet<>(inspector.connectedSetOf("a")).toString();
        }
        if (mode.equals("control")) {
            inspector.connectedSets();
            graph.addEdge("b", "c");
            return inspector.connectedSets().stream().map(TreeSet::new).toList()
                    + "/"
                    + inspector.pathExists("a", "c");
        }
        var before = new TreeSet<>(inspector.connectedSetOf("a"));
        graph.addEdge(directed ? "c" : "b", directed ? "b" : "c");
        return before
                + "->"
                + new TreeSet<>(inspector.connectedSetOf("a"))
                + "/"
                + new TreeSet<>(new ConnectivityInspector<>(graph).connectedSetOf("a"));
    }

    public static String observe(String[] a) {
        return run(a[0], false) + (a[0].equals("challenge") ? " / " + run(a[0], true) : "");
    }
}
