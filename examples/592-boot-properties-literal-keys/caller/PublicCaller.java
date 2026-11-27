import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.Properties;
import org.springframework.boot.env.PropertiesPropertySourceLoader;
import org.springframework.core.io.ByteArrayResource;

public class PublicCaller {
    public static String observe(String[] args) throws Exception {
        boolean control = args[0].equals("control");
        boolean challenge = args[0].equals("challenge");
        String indent = challenge ? "  " : "";
        String escape = control ? "" : "\\";
        String input = indent + escape + "#hash-prefixed=hash\n" + indent + escape + "!bang-prefixed=bang\n"
                + indent + "normal=ok\n" + (challenge ? "#hash-prefixed=wrong\n" : "");
        byte[] bytes = input.getBytes(StandardCharsets.US_ASCII);
        var doc = new PropertiesPropertySourceLoader().load("fixture", new ByteArrayResource(bytes)).getFirst();
        var independent = new Properties();
        independent.load(new ByteArrayInputStream(bytes));
        return doc.getProperty("#hash-prefixed") + "," + doc.getProperty("!bang-prefixed") + "," + doc.getProperty("normal")
                + " / " + independent.getProperty("#hash-prefixed") + "," + independent.getProperty("!bang-prefixed")
                + "," + independent.getProperty("normal");
    }
}
