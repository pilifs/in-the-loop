import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Properties;

/** The operator names the source, decoding API and requested keys. */
public class FilePropertiesHistory {
    public static String read(String path, boolean reader) {
        Properties p=new Properties();
        String stage="open";
        try (InputStream input=new FileInputStream(path)) {
            stage="load";
            if (reader) {
                try (Reader chars=new InputStreamReader(input, StandardCharsets.UTF_8)) { p.load(chars); }
            } else p.load(input);
            stage="read";
            StringBuilder result=new StringBuilder();
            for (String key:new String[]{"literal","escaped","continued","duplicate","absent"}) {
                String value=p.getProperty(key);
                result.append(key).append('=');
                if (value==null) result.append("missing");
                else value.chars().forEach(c->result.append(String.format("%04x",c)));
                result.append('|');
            }
            return result.toString();
        } catch (IOException|IllegalArgumentException e) { return stage+" "+e.getClass().getName(); }
    }
    public static void main(String[] args) { System.out.println(read(args[0],args[1].equals("reader"))); }
}
