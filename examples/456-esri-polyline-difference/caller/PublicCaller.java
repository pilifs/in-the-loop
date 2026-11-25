import com.esri.core.geometry.Geometry;
import com.esri.core.geometry.GeometryEngine;
import com.esri.core.geometry.GeometryException;
import com.esri.core.geometry.OperatorImportFromWkt;
import com.esri.core.geometry.Point;
import com.esri.core.geometry.Polyline;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public class PublicCaller {
    static final int[][] FIRST = {{117422,-64366}, {119336,-64652}, {119218,-65440},
            {114999,-64810}, {115034,-64578}, {115117,-64022}};
    static final int[][] REMOTE = {{111611,-62617}, {111365,-64268}, {110476,-64135},
            {110722,-62484}, {110975,-62522}};
    static final int[] T = {117911,-61089};

    static String path(int[][] points, boolean closed) {
        List<String> coords = new ArrayList<>();
        for (int[] p : points) coords.add(p[0] + " " + p[1]);
        if (closed) coords.add(coords.get(0));
        return "(" + String.join(",", coords) + ")";
    }

    static Polyline read(String wkt) {
        return (Polyline) OperatorImportFromWkt.local().execute(0, Geometry.Type.Polyline, wkt, null);
    }

    static class Edge {
        final double x, y, dx, dy;

        Edge(double x, double y, double endX, double endY) {
            this.x = x;
            this.y = y;
            this.dx = endX - x;
            this.dy = endY - y;
        }

        double length() {
            return Math.hypot(dx, dy);
        }

        boolean onLine(double px, double py) {
            return Math.abs(dx * (py - y) - dy * (px - x)) <= 1e-8 * length();
        }

        // Sweep the dominant coordinate. Counts apply to open intervals, so touching at
        // one point changes nothing and adjacent collinear pieces can cover one edge.
        int[] coverage(List<Edge> others) {
            boolean horizontal = Math.abs(dx) >= Math.abs(dy);
            double a = horizontal ? x : y, b = a + (horizontal ? dx : dy);
            double begin = Math.min(a, b), end = Math.max(a, b);
            TreeMap<Double,Integer> events = new TreeMap<>();
            events.put(begin, 0);
            events.put(end, 0);
            for (Edge e : others) {
                if (!onLine(e.x, e.y) || !onLine(e.x + e.dx, e.y + e.dy)) continue;
                double p = horizontal ? e.x : e.y, q = p + (horizontal ? e.dx : e.dy);
                double lo = Math.max(begin, Math.min(p, q)), hi = Math.min(end, Math.max(p, q));
                if (lo < hi) {
                    events.merge(lo, 1, Integer::sum);
                    events.merge(hi, -1, Integer::sum);
                }
            }
            int min = Integer.MAX_VALUE, max = 0, active = 0;
            for (Map.Entry<Double,Integer> event : events.entrySet()) {
                if (event.getKey() == end) break;
                active += event.getValue();
                min = Math.min(min, active);
                max = Math.max(max, active);
            }
            return new int[]{min, max};
        }
    }

    static List<Edge> loop(int[][] coords) {
        List<Edge> edges = new ArrayList<>();
        for (int i = 0; i < coords.length; i++) {
            int[] a = coords[i], b = coords[(i + 1) % coords.length];
            edges.add(new Edge(a[0], a[1], b[0], b[1]));
        }
        return edges;
    }

    static void add(List<Edge> edges, Point a, Point b) {
        if (a.getX() != b.getX() || a.getY() != b.getY())
            edges.add(new Edge(a.getX(), a.getY(), b.getX(), b.getY()));
    }

    static List<Edge> segments(Polyline line) {
        List<Edge> edges = new ArrayList<>();
        for (int path = 0; path < line.getPathCount(); path++) {
            int start = line.getPathStart(path), end = line.getPathEnd(path);
            for (int i = start + 1; i < end; i++) add(edges, line.getPoint(i - 1), line.getPoint(i));
            if (line.isClosedPath(path) && end > start) add(edges, line.getPoint(end - 1), line.getPoint(start));
        }
        return edges;
    }

    static List<String> counts(List<Edge> reference, List<Edge> actual) {
        List<String> result = new ArrayList<>();
        for (Edge edge : reference) {
            int[] coverage = edge.coverage(actual);
            result.add(coverage[0] == coverage[1] ? Integer.toString(coverage[0]) : coverage[0] + ".." + coverage[1]);
        }
        return result;
    }

    static String subtract(boolean open, int[]... subtractor) {
        String leftWkt = open ? "LINESTRING" + path(FIRST, false)
                : "MULTILINESTRING(" + path(FIRST, true) + "," + path(REMOTE, true) + ")";
        Polyline left = read(leftWkt);
        Polyline right = read("LINESTRING" + path(subtractor, false));
        double expectedLength = left.calculateLength2D();
        if (subtractor.length == 3) expectedLength -= Math.hypot(1914, -286);
        Polyline result;
        try {
            result = (Polyline) GeometryEngine.difference(left, right, null);
        } catch (GeometryException e) {
            return "throws:" + e.getClass().getName();
        }
        List<Edge> actual = segments(result);
        List<Edge> first = loop(FIRST), remote = loop(REMOTE), reference = new ArrayList<>(first);
        reference.addAll(remote);
        int extra = 0;
        for (Edge edge : actual) if (edge.coverage(reference)[0] == 0) extra++;
        double length = result.calculateLength2D();
        return "first=" + counts(first, actual) + " remote=" + counts(remote, actual) + " extra=" + extra
                + " lengthOK=" + (Math.abs(length - expectedLength) <= 1e-7)
                + " length=" + length + " expected=" + expectedLength;
    }

    public static String observe(String[] args) {
        switch (args[0]) {
        case "touch":
            return "forward=" + subtract(false, FIRST[0], T) + " | reverse=" + subtract(false, T, FIRST[0]);
        case "open":
            return subtract(true, FIRST[0], T);
        case "overlap":
            return subtract(false, T, FIRST[0], FIRST[1]);
        default:
            throw new IllegalArgumentException(Arrays.toString(args));
        }
    }
}
