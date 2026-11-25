import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import com.badlogic.gdx.math.Intersector;
import com.badlogic.gdx.math.Polygon;
import com.badlogic.gdx.math.Rectangle;

public class PublicCaller {
    static Polygon rectangle(float x1, float y1, float x2, float y2) {
        return new Polygon(new float[]{x1,y1, x1,y2, x2,y2, x2,y1});
    }

    static String clip(Polygon subject, Polygon mask, Polygon output) {
        try {
            return Boolean.toString(Intersector.intersectPolygons(subject, mask, output));
        } catch (IllegalArgumentException e) {
            return e.getClass().getName();
        }
    }

    static String bounds(Polygon polygon) {
        Rectangle r = polygon.getBoundingRectangle();
        return r.x + "," + r.y + "," + r.width + "," + r.height;
    }

    static String geometry(Polygon polygon) {
        float[] coordinates = polygon.getVertices();
        List<String> pairs = new ArrayList<>();
        for (int i = 0; i < coordinates.length; i += 2) pairs.add(coordinates[i] + "," + coordinates[i + 1]);
        Collections.sort(pairs);
        return polygon.getVertexCount() + "/" + pairs + "/" + bounds(polygon);
    }

    public static String observe(String[] args) {
        if (args[0].equals("triangle")) {
            Polygon subject = new Polygon(new float[]{3200.1453f,88.00839f, 3233.9087f,190.34174f, 3266.2905f,0});
            Polygon mask = new Polygon(new float[]{3213,131, 3214,131, 3214,130, 3213,130});
            Polygon fresh = new Polygon();
            return "fresh=" + clip(subject, mask, fresh) + " vertices=" + fresh.getVertexCount()
                    + " null=" + clip(subject, mask, null);
        }
        Polygon subject = rectangle(1, 2, 3, 5);
        Polygon mask = rectangle(0, 0, 10, 10);
        Polygon fresh = new Polygon();
        String control = clip(subject, mask, fresh) + "/" + geometry(fresh);
        if (args[0].equals("inside")) return control;
        Polygon used = rectangle(-4, -4, -2, -2);
        String before = bounds(used);
        return "fresh=" + control + " before=" + before + " reused=" + clip(subject, mask, used) + "/" + geometry(used);
    }
}
