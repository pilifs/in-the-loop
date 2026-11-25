import java.util.Collections;
import java.util.List;
import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversal;
import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import org.apache.tinkerpop.gremlin.tinkergraph.structure.TinkerFactory;
import org.apache.tinkerpop.gremlin.tinkergraph.structure.TinkerGraph;

public class PublicCaller {
    public static String observe(String[] args) throws Exception {
        try (TinkerGraph graph = TinkerFactory.createModern(); GraphTraversalSource g = graph.traversal()) {
            GraphTraversal<Vertex, Vertex> traversal = g.V().dedup().by("age");
            if (!args[0].equals("age")) {
                if (args[0].equals("twoSteps")) traversal = traversal.dedup();
                try {
                    traversal.by("name");
                } catch (IllegalStateException e) {
                    return "by threw " + e.getClass().getName();
                }
            }
            try {
                List<String> names = traversal.<String>values("name").toList();
                Collections.sort(names);
                return "iterated " + names;
            } catch (IllegalStateException e) {
                return "iteration threw " + e.getClass().getName();
            }
        }
    }
}
