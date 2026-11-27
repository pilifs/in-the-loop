import java.nio.charset.StandardCharsets;

public class LaunchMarkers {
    static String marker(String name) throws Exception {
        try (var in = Thread.currentThread().getContextClassLoader().getResourceAsStream(name)) {
            return in == null ? "absent" : new String(in.readAllBytes(),StandardCharsets.UTF_8);
        }
    }
    public static void main(String[] args) throws Exception {
        System.out.println("MARKERS " + marker("regular-marker.txt") + "/" + marker("provided-marker.txt"));
    }
}
