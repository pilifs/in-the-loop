import java.io.InputStream;
import java.net.URL;
import java.util.Enumeration;

public final class ResourceChoices {
    public static void main(String[] args) throws Exception {
        for (String name : new String[] {"META-INF/missing", "META-INF/paint"}) {
            ClassLoader loader = PairResourceGate.class.getClassLoader();
            Enumeration<URL> candidates = loader.getResources(name);
            int firstByte = -1;
            String selected = "absent";
            if (candidates.hasMoreElements()) {
                URL resource = candidates.nextElement();
                selected = resource.toExternalForm();
                try (InputStream input = resource.openStream()) {
                    firstByte = input.read();
                }
            }
            int returned = PairResourceGate.read(name.equals("META-INF/paint"));
            System.out.println(name + "\t" + selected + "\t" + firstByte + "\t" + returned);
        }
    }
}
