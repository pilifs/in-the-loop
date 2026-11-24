import java.io.StringReader;
import javax.xml.parsers.DocumentBuilderFactory;
import org.xml.sax.InputSource;
import org.commonmark.node.Code;
import org.commonmark.node.Node;
import org.commonmark.parser.Parser;
import org.commonmark.renderer.html.HtmlRenderer;
import org.w3c.dom.Element;

public class UpgradeProbe {
    private static Code firstCode(Node node) {
        if (node instanceof Code) return (Code) node;
        for (Node child = node.getFirstChild(); child != null; child = child.getNext()) {
            Code code = firstCode(child);
            if (code != null) return code;
        }
        return null;
    }
    private static String attributes(String html) throws Exception {
        var doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(new InputSource(new StringReader(html)));
        Element image = (Element)doc.getElementsByTagName("img").item(0);
        String escaped = html.substring(html.indexOf("alt=\"") + 5);
        escaped = escaped.substring(0, escaped.indexOf('"'));
        return image.getAttribute("src") + "/" + image.getAttribute("alt") + "/" + escaped
                + "/" + doc.getElementsByTagName("code").item(0).getTextContent();
    }
    public static String observe(String[] args) throws Exception {
        Parser parser = Parser.builder().build();
        HtmlRenderer renderer = HtmlRenderer.builder().build();
        boolean text = args[0].equals("markup");
        String literal = args[0].equals("entities") ? "x & y" : "foo";
        char tick = 96;
        String label = text ? "plain *bold* [link](else)" : tick + literal + tick + (args[0].equals("mixed") ? " bar" : "");
        Node tree = parser.parse("![" + label + "](cover.png) " + tick + "outside" + tick);
        String before = attributes(renderer.render(tree));
        firstCode(tree).setLiteral(text ? "outside & edited" : "edit & again");
        return before + "|" + attributes(renderer.render(tree));
    }
}
