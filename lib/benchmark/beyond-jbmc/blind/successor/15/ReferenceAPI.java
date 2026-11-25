import org.codehaus.plexus.metadata.merge.ComponentsXmlMerger;
import org.jdom2.Document;
import org.jdom2.Element;

public final class ReferenceAPI {
    private static Document doc(String role) {
        Element root = new Element("component-set");
        Element comps = new Element("components"), component = new Element("component");
        root.addContent(comps); comps.addContent(component);
        component.addContent(new Element("role").setText(role));
        component.addContent(new Element("role-hint").setText("hint"));
        component.addContent(new Element("implementation").setText("fixture.Impl"));
        return new Document(root);
    }
    public static long primary(int n) throws Exception {
        Document d = new ComponentsXmlMerger().merge(doc("A"), doc(n == 0 ? "A" : "B"));
        return d.getRootElement().getChild("components").getChildren("component").size();
    }
    public static long control(int n) throws Exception {
        Document a = doc("A");
        Document d = new ComponentsXmlMerger().merge(a, doc("A"));
        return d == a && "A".equals(d.getRootElement().getChild("components").getChild("component").getChildText("role")) ? 1 : 0;
    }
}
