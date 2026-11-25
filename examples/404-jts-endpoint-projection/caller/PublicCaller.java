import java.util.Arrays;
import org.locationtech.jts.geom.*;
import org.locationtech.jtstest.function.LineSegmentFunctions;

public class PublicCaller {
    static final LineSegment target = new LineSegment(0, 0, 8, 0);

    static String xy(Coordinate c) {
        return "(" + Double.toString(c.x).replaceFirst("\\.0$", "") + ","
                   + Double.toString(c.y).replaceFirst("\\.0$", "") + ")";
    }

    static LineSegment source(int x) { return new LineSegment(x, 2, x, 4); }

    static String project(int x) {
        LineSegment p = target.project(source(x));
        return p == null ? "null" : xy(p.getCoordinate(0)) + " " + xy(p.getCoordinate(1));
    }

    static String geometry(int x) {
        var factory = new GeometryFactory();
        Geometry p = LineSegmentFunctions.project(target.toGeometry(factory), source(x).toGeometry(factory));
        return p.getGeometryType() + " " + p.getLength() + " "
                + Arrays.stream(p.getCoordinates()).map(PublicCaller::xy).toList();
    }

    public static String observe(String[] args) {
        return switch (args[0]) {
            case "contact" -> project(8);
            case "inside-outside" -> project(1) + "; " + project(9);
            case "geometry" -> geometry(8) + "; " + geometry(9);
            default -> throw new IllegalArgumentException();
        };
    }
}
