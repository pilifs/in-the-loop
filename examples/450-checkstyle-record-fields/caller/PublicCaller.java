import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;
import com.puppycrawl.tools.checkstyle.Main;
import com.puppycrawl.tools.checkstyle.checks.coding.HiddenFieldCheck;

public class PublicCaller {
    static void checkProvider(Path log, Class<?> type) throws Exception {
        String name = "] " + type.getName() + " source: ";
        Path expected = Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI());
        List<Path> origins = new ArrayList<>();
        for (String line : Files.readAllLines(log)) {
            int start = line.indexOf(name);
            if (start >= 0) origins.add(Path.of(java.net.URI.create(line.substring(start + name.length()))));
        }
        if (!origins.equals(List.of(expected))) throw new IllegalStateException("CLI provider for " + type.getName());
    }

    static String audit(String variant) throws Exception {
        Path dir = Files.createDirectory(Path.of(variant));
        Path source = dir.resolve("Sample.java");
        List<String> lines = new ArrayList<>();
        lines.add("class Sample {");
        lines.add("  int quota;");
        boolean nested = variant.endsWith("-nested");
        if (nested) lines.add("  static int limit;");
        String declaration = variant.equals("class") ? "class Entry" :
                (variant.startsWith("static-") ? "static record Entry()" : "record Entry()");
        lines.add("  " + declaration + " {");
        lines.add("    int take(int quota) { return quota; }");
        if (nested) lines.add("    class Reader { int cap(int limit) { return limit; } }");
        lines.add("  }");
        lines.add("}");
        Files.write(source, lines);
        Path xml = dir.resolve("audit.xml"), log = dir.resolve("classes.log");
        Process child = new ProcessBuilder(Path.of(System.getProperty("java.home"), "bin/java").toString(),
                "-Xmx128m", "-XX:-UsePerfData", "-Duser.language=en", "-Duser.country=US",
                "-Xlog:class+load=info:file=" + log, "-cp", System.getProperty("java.class.path"),
                Main.class.getName(), "-c", "fixtures/hidden.xml", "-f", "xml", "-o", xml.toString(), source.toString())
                .redirectErrorStream(true).redirectOutput(dir.resolve("console.txt").toFile()).start();
        int exit = child.waitFor();
        checkProvider(log, Main.class);
        checkProvider(log, HiddenFieldCheck.class);
        DocumentBuilderFactory parser = DocumentBuilderFactory.newInstance();
        parser.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Element root = parser.newDocumentBuilder().parse(xml.toFile()).getDocumentElement();
        NodeList files = root.getElementsByTagName("file");
        if (files.getLength() != 1 || !Files.isSameFile(source, Path.of(((Element) files.item(0)).getAttribute("name")))) {
            throw new IllegalStateException("CLI audited a different file");
        }
        List<String> diagnostics = new ArrayList<>();
        NodeList errors = root.getElementsByTagName("error");
        for (int i = 0; i < errors.getLength(); i++) {
            Element error = (Element) errors.item(i);
            int row = Integer.parseInt(error.getAttribute("line"));
            int column = Integer.parseInt(error.getAttribute("column"));
            String line = lines.get(row - 1);
            int start = column - 1, end = start;
            while (end < line.length() && Character.isJavaIdentifierPart(line.charAt(end))) end++;
            String check = error.getAttribute("source");
            diagnostics.add(check + "/" + line.substring(start, end) + "@" + row + ":" + column);
        }
        return exit + "/" + diagnostics;
    }

    public static String observe(String[] args) throws Exception {
        if (args[0].equals("boundaries")) return audit("implicit-nested") + " | " + audit("static-nested");
        return audit(args[0]);
    }
}
