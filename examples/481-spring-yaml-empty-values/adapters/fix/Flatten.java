import java.util.Map;
import org.springframework.beans.factory.config.YamlProcessor;

class Flatten extends YamlProcessor {
    Map<String, Object> select(Map<String, Object> source, Object marker) {
        return getFlattenedMap(source, true, marker);
    }

    boolean canSelectMarker() {
        return true;
    }
}
