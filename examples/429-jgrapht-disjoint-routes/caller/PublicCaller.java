import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import org.jgrapht.GraphPath;
import org.jgrapht.alg.shortestpath.*;
import org.jgrapht.graph.*;

public class PublicCaller {
    static String solve(boolean bhandari, int k, boolean tie) {
        var graph = new SimpleDirectedWeightedGraph<Integer,DefaultWeightedEdge>(DefaultWeightedEdge.class);
        for (int i = 1; i <= 8; i++) graph.addVertex(i);
        int[][] arcs = {{1,3,1},{1,4,1},{1,5,1},{6,2,1},{7,2,1},{8,2,1},
                {3,6,2},{3,7,1},{4,7,6},{4,6,5},{5,7,tie ? 1 : 3},{5,8,6}};
        for (var a : arcs) graph.setEdgeWeight(graph.addEdge(a[0], a[1]), a[2]);
        try {
            List<GraphPath<Integer,DefaultWeightedEdge>> paths = bhandari
                    ? new BhandariKDisjointShortestPaths<>(graph).getPaths(1,2,k)
                    : new SuurballeKDisjointShortestPaths<>(graph).getPaths(1,2,k);
            var seen = new HashSet<DefaultWeightedEdge>();
            var output = new ArrayList<String>();
            var missing = new ArrayList<String>();
            for (var path : paths) {
                double total = 0;
                var vertices = path.getVertexList();
                boolean original = path.getEdgeList().size() == vertices.size() - 1;
                for (int i = 0; i < path.getEdgeList().size(); i++) {
                    var e = path.getEdgeList().get(i);
                    if (!graph.containsEdge(e)) missing.add(vertices.get(i) + "->" + vertices.get(i+1));
                    original &= graph.containsEdge(e) && seen.add(e)
                            && graph.getEdgeSource(e).equals(vertices.get(i))
                            && graph.getEdgeTarget(e).equals(vertices.get(i+1));
                    var inputEdge = graph.getEdge(vertices.get(i), vertices.get(i+1));
                    total += inputEdge == null ? Double.NaN : graph.getEdgeWeight(inputEdge);
                }
                output.add(vertices + "@" + path.getWeight() + "/" + (original && total == path.getWeight()));
            }
            return output + (missing.isEmpty() ? "" : " missingFromInputGraph=" + missing);
        } catch (RuntimeException ex) { return ex.getClass().getName(); }
    }
    public static String observe(String[] args) {
        int k = args[0].equals("one") ? 1 : 3;
        return solve(false,k,args[0].equals("tie")) + " | " + solve(true,k,args[0].equals("tie"));
    }
}
