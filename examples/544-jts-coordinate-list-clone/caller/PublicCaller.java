import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.CoordinateList;

import java.util.*;

public class PublicCaller {
    static String points(CoordinateList list) {
        List<String> result = new ArrayList<>();
        for (Coordinate p : list.toCoordinateArray(true)) result.add((int) p.x + ":" + (int) p.y);
        return result.toString();
    }

    static CoordinateList list(int... xs) {
        CoordinateList c = new CoordinateList();
        for (int x : xs) c.add(new Coordinate(x, x), true);
        return c;
    }

    public static String observe(String[] a) {
        var orig =
                switch (a[0]) {
                    case "control" -> list();
                    case "challenge" -> list(1, 1);
                    default -> list(0, 1, 2);
                };
        var clone = (CoordinateList) orig.clone();
        if (a[0].equals("control")) {
            clone.add(new Coordinate(4, 5));
            return orig.size() + "/" + points(clone);
        }
        if (a[0].equals("challenge")) {
            clone.getCoordinate(0).x = 9;
            return points(clone) + "/" + points(orig);
        }
        String initial = points(clone);
        clone.getCoordinate(1).x = 9;
        return "size="
                + clone.size()
                + ",points="
                + initial
                + ",original="
                + (int) orig.getCoordinate(1).x;
    }
}
