import java.io.*;
import java.util.regex.Pattern;
import javax.xml.stream.*;
import org.codehaus.stax2.XMLStreamWriter2;
import com.ctc.wstx.api.InvalidCharHandler;
import com.ctc.wstx.api.WstxOutputProperties;
import com.ctc.wstx.stax.WstxOutputFactory;

public class PublicCaller {
    public static String observe(String[] args) throws Exception {
        boolean safe = args[0].equals("safe"), repair = args[0].equals("repair");
        boolean diagnostic = args[0].equals("diagnostic");
        var factory = new WstxOutputFactory();
        factory.setProperty(WstxOutputProperties.P_OUTPUT_VALIDATE_CONTENT, true);
        factory.setProperty(WstxOutputProperties.P_OUTPUT_FIX_CONTENT, repair);
        if (diagnostic) factory.setProperty(WstxOutputProperties.P_OUTPUT_INVALID_CHAR_HANDLER,
                new InvalidCharHandler.ReplacingHandler('x'));
        String selected = repair ? "A]]>B]]>C" : (diagnostic ? (char) 1 : 'X') + "]]>Y";
        char[] chars = (safe ? "PPPP OK]]>" : "PPPP" + selected + "QQ").toCharArray();
        var output = new StringWriter();
        var writer = (XMLStreamWriter2) factory.createXMLStreamWriter(output);
        writer.writeStartElement("root");
        try { writer.writeCData(chars, safe ? 5 : 4, safe ? 2 : selected.length()); }
        catch (XMLStreamException error) {
            var index = Pattern.compile("\\(index (\\d+)\\)").matcher(error.getMessage());
            return "XMLStreamException index=" + (index.find() ? index.group(1) : "unreported");
        }
        writer.writeEndElement();
        writer.writeEndDocument();
        writer.close();
        var reader = XMLInputFactory.newDefaultFactory().createXMLStreamReader(new StringReader(output.toString()));
        try {
            reader.nextTag();
            return reader.getElementText();
        } finally { reader.close(); }
    }
}
