import org.jgrapht.alg.tour.FarthestInsertionHeuristicTSP;
import org.jgrapht.graph.*;

import java.util.*;

public class PublicCaller {
    public static String observe(String[] a) {
        boolean four = a[0].equals("challenge");
        double[] weights =
                four
                        ? new double[] {10, -3, -2, -5, -4, -1}
                        : a[0].equals("control")
                                ? new double[] {2, 3, 4}
                                : new double[] {-3, -2, -1};
        int n = four ? 4 : 3, k = 0;
        var g = new SimpleWeightedGraph<Integer, DefaultWeightedEdge>(DefaultWeightedEdge.class);
        for (int i = 0; i < n; i++) g.addVertex(i);
        for (int i = 0; i < n; i++)
            for (int j = i + 1; j < n; j++) g.setEdgeWeight(g.addEdge(i, j), weights[k++]);
        var tour = new FarthestInsertionHeuristicTSP<Integer, DefaultWeightedEdge>().getTour(g);
        var vs = tour.getVertexList();
        boolean vertices =
                vs.size() == n + 1
                        && Objects.equals(vs.get(0), vs.get(n))
                        && new HashSet<>(vs.subList(0, n)).equals(g.vertexSet());
        double sum = 0;
        boolean edges = tour.getEdgeList().size() == n;
        for (int i = 1; i < vs.size(); i++) {
            var edge = g.getEdge(vs.get(i - 1), vs.get(i));
            edges &= edge != null && edge.equals(tour.getEdgeList().get(i - 1));
            if (edge != null) sum += g.getEdgeWeight(edge);
        }
        return "vertices="
                + vertices
                + ",edges="
                + edges
                + (four
                        ? ",weightAgrees=" + (tour.getWeight() == sum)
                        : ",weight=" + tour.getWeight() + ",sum=" + sum);
    }
}
