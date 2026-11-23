// Setup probe (evaluation side only, not an input to any automatic lane): the brief's JGraphT 1.5.2 census.
// Every acyclic subset of the six ordered non-self arcs on {a,b,c}, built through public calls in lexicographic arc order;
// each arc tried with a fresh DefaultEdge on a fresh copy; outcome predicted by transitive closure; edges and endpoints compared.
import org.jgrapht.graph.*; import java.util.*;
public final class DagCensus {
    static final String[] V = {"a", "b", "c"};
    static final int[][] ARCS = {{0,1},{0,2},{1,0},{1,2},{2,0},{2,1}};
    static boolean reach(boolean[][] e, int s, int t) { boolean[] seen = new boolean[3]; Deque<Integer> q = new ArrayDeque<>(List.of(s));
        while (!q.isEmpty()) { int u = q.pop(); if (u == t) return true; if (seen[u]) continue; seen[u] = true; for (int w = 0; w < 3; w++) if (e[u][w]) q.push(w); } return false; }
    static DirectedAcyclicGraph<String, DefaultEdge> build(int mask, Map<Integer, DefaultEdge> edges) {
        DirectedAcyclicGraph<String, DefaultEdge> g = new DirectedAcyclicGraph<>(null, null, false);
        for (String v : V) g.addVertex(v);
        for (int i = 0; i < 6; i++) if ((mask >> i & 1) != 0) { DefaultEdge d = new DefaultEdge(); if (!g.addEdge(V[ARCS[i][0]], V[ARCS[i][1]], d)) throw new AssertionError(); edges.put(i, d); }
        return g; }
    public static void main(String[] a) {
        int graphs = 0, ins = 0, dup = 0, cyc = 0, mismatch = 0;
        for (int mask = 0; mask < 64; mask++) {
            boolean[][] e = new boolean[3][3]; for (int i = 0; i < 6; i++) if ((mask >> i & 1) != 0) e[ARCS[i][0]][ARCS[i][1]] = true;
            boolean acyclic = true; for (int i = 0; i < 6; i++) if (e[ARCS[i][0]][ARCS[i][1]] && reach(e, ARCS[i][1], ARCS[i][0])) acyclic = false;
            if (!acyclic) continue; graphs++;
            for (int k = 0; k < 6; k++) {
                int s = ARCS[k][0], t = ARCS[k][1]; String want = e[s][t] ? "dup" : reach(e, t, s) ? "cycle" : "insert";
                Map<Integer, DefaultEdge> edges = new HashMap<>(); DirectedAcyclicGraph<String, DefaultEdge> g = build(mask, edges);
                DefaultEdge fresh = new DefaultEdge(); String got;
                try { got = g.addEdge(V[s], V[t], fresh) ? "insert" : "dup"; } catch (IllegalArgumentException x) { got = "cycle"; }
                boolean ok = got.equals(want) && g.edgeSet().size() == edges.size() + (got.equals("insert") ? 1 : 0);
                for (Map.Entry<Integer, DefaultEdge> en : edges.entrySet()) ok &= g.containsEdge(en.getValue()) && g.getEdgeSource(en.getValue()) == V[ARCS[en.getKey()][0]] && g.getEdgeTarget(en.getValue()) == V[ARCS[en.getKey()][1]];
                if (got.equals("insert")) ok &= g.getEdgeSource(fresh) == V[s] && g.getEdgeTarget(fresh) == V[t]; else ok &= !g.containsEdge(fresh);
                if (!ok) mismatch++;
                if (got.equals("insert")) ins++; else if (got.equals("dup")) dup++; else cyc++;
            }
        }
        System.out.println("graphs=" + graphs + " transitions=" + (ins + dup + cyc) + " insert=" + ins + " duplicate=" + dup + " cycle=" + cyc + " oracleMismatches=" + mismatch);
        // identity control on a single-edge graph a->b
        Map<Integer, DefaultEdge> one = new HashMap<>(); DirectedAcyclicGraph<String, DefaultEdge> g = build(1, one); DefaultEdge e0 = one.get(0);
        String r1, r2, r3;
        try { r1 = "returned " + g.addEdge("x", "b", e0); } catch (RuntimeException x) { r1 = "threw " + x.getClass().getSimpleName(); }
        try { r2 = "returned " + g.addEdge("x", "b", new DefaultEdge()); } catch (RuntimeException x) { r2 = "threw " + x.getClass().getSimpleName(); }
        try { r3 = "returned " + g.addEdge("a", "c", null); } catch (RuntimeException x) { r3 = "threw " + x.getClass().getSimpleName(); }
        System.out.println("existing edge, unregistered source: " + r1 + "; fresh edge, unregistered source: " + r2 + "; null edge, valid endpoints: " + r3
            + "; after: vertices=" + g.vertexSet() + " edges=" + g.edgeSet().size() + " e0=" + g.getEdgeSource(e0) + "->" + g.getEdgeTarget(e0));
    }
}
