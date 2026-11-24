import org.jgrapht.graph.AsWeightedGraph;
import org.jgrapht.graph.DefaultWeightedEdge;
import org.jgrapht.graph.SimpleWeightedGraph;

public class UpgradeProbe {
    public static String observe(String[] args) {
        boolean enabled = args[0].equals("on"), cached = args[1].equals("cached"), through = !args[2].equals("local");
        UpgradeProbe.class.getClassLoader().setDefaultAssertionStatus(enabled);
        SimpleWeightedGraph<String,DefaultWeightedEdge> base = new SimpleWeightedGraph<>(DefaultWeightedEdge.class);
        base.addVertex("u"); base.addVertex("v");
        DefaultWeightedEdge edge = base.addEdge("u","v");
        base.setEdgeWeight(edge, 2);
        AsWeightedGraph<String,DefaultWeightedEdge> view = new AsWeightedGraph<>(base, e -> 7.0, cached, through);
        if (view.getClass().desiredAssertionStatus() != enabled) throw new AssertionError("wrong product assertion profile");
        StringBuilder out = new StringBuilder();
        for (double value : new double[]{9,11}) {
            String status = "returned";
            try { view.setEdgeWeight(edge, value); }
            catch (UnsupportedOperationException | AssertionError e) { status = e.getClass().getSimpleName(); }
            if (out.length() > 0) out.append('|');
            out.append(status).append('/').append(view.getEdgeWeight(edge)).append('/').append(base.getEdgeWeight(edge));
        }
        return out.toString();
    }
}
