import org.dom4j.*;
import org.dom4j.io.XMLWriter;
import java.io.*;
public final class ReferenceAPI {
    static String output(String word) throws IOException {
        Element root=DocumentHelper.createElement("r");root.addText(word);
        StringWriter buffer=new StringWriter();XMLWriter serializer=new XMLWriter(buffer);serializer.write(root);serializer.flush();
        return buffer.toString();
    }
    public static long primary(int n) throws IOException {
        String word=n==0?"a&b":"a<b",text=output(word);
        try {return text.equals(n==0?"<r>a&amp;b</r>":"<r>a&lt;b</r>") && DocumentHelper.parseText(text).getRootElement().getText().equals(word)?1:0;}
        catch(DocumentException e){return 0;}
    }
    public static long control(int n) throws IOException {return output("abc").equals("<r>abc</r>")?1:0;}
}
