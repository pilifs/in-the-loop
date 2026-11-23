import java.util.Arrays;
import java.util.List;
import org.jgrapht.Graph;

/** Independent oracle, invoked only after a transition. Every comparison uses the actual objects. */
public final class GraphAudit implements ActionCensus.Audit {
    public void check(Object root, Object[] vertices, List<ActionCensus.Arc> history,
                      ActionCensus.Arc attempt, String outcome) {
        @SuppressWarnings("unchecked")
        Graph<Object,Object> graph = (Graph<Object,Object>) root;
        List<Object> labels = Arrays.asList(vertices);
        boolean[][] arcs = new boolean[vertices.length][vertices.length];
        for (var arc : history) arcs[labels.indexOf(arc.source())][labels.indexOf(arc.target())] = true;
        boolean[][] paths = new boolean[arcs.length][];
        for (int i = 0; i < arcs.length; i++) paths[i] = arcs[i].clone();
        for (int k = 0; k < arcs.length; k++)
            for (int i = 0; i < arcs.length; i++)
                for (int j = 0; j < arcs.length; j++) paths[i][j] |= paths[i][k] && paths[k][j];
        int s = labels.indexOf(attempt.source()), t = labels.indexOf(attempt.target());
        boolean duplicate = arcs[s][t], cycle = paths[t][s];
        boolean insert = !duplicate && !cycle;
        boolean decision = insert ? outcome.equals("true") : duplicate ? outcome.equals("false")
            : outcome.equals("throws:org.jgrapht.graph.GraphCycleProhibitedException")
                || outcome.equals("throws:java.lang.IllegalArgumentException");
        boolean identities = graph.vertexSet().size() == labels.size()
            && labels.stream().allMatch(label -> graph.vertexSet().stream().anyMatch(v -> v == label))
            && graph.edgeSet().size() == history.size() + (insert ? 1 : 0);
        for (var edge : history) identities &= graph.containsEdge(edge.edge())
            && graph.getEdge(edge.source(), edge.target()) == edge.edge()
            && graph.getEdgeSource(edge.edge()) == edge.source() && graph.getEdgeTarget(edge.edge()) == edge.target();
        if (insert) identities &= graph.containsEdge(attempt.edge())
            && graph.getEdgeSource(attempt.edge()) == attempt.source() && graph.getEdgeTarget(attempt.edge()) == attempt.target();
        else identities &= !graph.containsEdge(attempt.edge());
        if (!decision || !identities) {
            int mask = 0;
            for (var arc : history) mask |= 1 << arc.number();
            System.out.println("mismatch\t" + mask + "\t" + attempt.number() + "\t" + outcome
                + "\texpected=" + (insert ? "insert" : duplicate ? "duplicate" : "cycle") + "\tidentities=" + identities);
        }
    }
}
