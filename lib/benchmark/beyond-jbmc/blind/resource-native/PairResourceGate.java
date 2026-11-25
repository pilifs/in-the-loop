import java.io.InputStream;
import java.net.URL;
import java.util.Enumeration;

public class PairResourceGate {
    public static int read(boolean selected) throws Exception {
        String name = selected ? "META-INF/paint" : "META-INF/missing";
        ClassLoader loader = PairResourceGate.class.getClassLoader();
        Enumeration<URL> resources = loader.getResources(name);
        if (!resources.hasMoreElements()) return -1;
        try (InputStream input = resources.nextElement().openStream()) {
            int value = input.read();
            return value;
        }
    }

    public static void main(String[] args) throws Exception {
        System.out.println(read(false) + "," + read(true));
    }
}
