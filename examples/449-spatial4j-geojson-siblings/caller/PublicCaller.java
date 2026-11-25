import java.util.*;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.locationtech.jts.geom.*;
import org.locationtech.spatial4j.io.jackson.ShapesAsGeoJSONModule;

public class PublicCaller {
    // Normalize object order and equivalent number spellings, preserving every field and array element.
    static String tree(JsonNode node) {
        if (node.isObject()) {
            SortedMap<String,String> fields = new TreeMap<>();
            node.fields().forEachRemaining(e -> fields.put(e.getKey(), tree(e.getValue())));
            return fields.toString();
        }
        if (node.isArray()) {
            List<String> children = new ArrayList<>();
            node.forEach(child -> children.add(tree(child)));
            return children.toString();
        }
        return node.isNumber() ? node.decimalValue().stripTrailingZeros().toPlainString() : node.toString();
    }

    static String write(ObjectMapper writer, Object object) throws Exception {
        String json;
        try {
            json = writer.writeValueAsString(object);
        } catch (JsonProcessingException e) {
            Throwable root = e;
            while (root.getCause() != null) root = root.getCause();
            return "write=" + e.getClass().getName() + " root=" + root.getClass().getName();
        }
        return tree(new ObjectMapper().readTree(json));
    }

    public static String observe(String[] args) throws Exception {
        ObjectMapper writer = new ObjectMapper().registerModule(new ShapesAsGeoJSONModule());
        GeometryFactory factory = new GeometryFactory();
        Point point = factory.createPoint(new Coordinate(100, 100));
        MultiPoint multi = factory.createMultiPoint(new Point[]{point});
        if (!args[0].equals("nested")) {
            return write(writer, Collections.singletonList(args[0].equals("point") ? point : multi));
        }
        Point sibling = factory.createPoint(new Coordinate(7, 9));
        List<String> results = new ArrayList<>();
        for (Geometry[] order : new Geometry[][]{{multi, sibling}, {sibling, multi}}) {
            Map<String,Object> envelope = new LinkedHashMap<>();
            envelope.put("geometry", factory.createGeometryCollection(order));
            envelope.put("after", 17);
            results.add(write(writer, envelope));
        }
        return String.join(" | ", results);
    }
}
