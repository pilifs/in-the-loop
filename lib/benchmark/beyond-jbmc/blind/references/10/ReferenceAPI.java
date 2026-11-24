import org.htmlcleaner.HtmlCleaner;
import org.htmlcleaner.TagNode;
public final class ReferenceAPI {
    public static long primary(int n) {
        TagNode tree=new HtmlCleaner().clean("<p><svg xmlns='http://www.w3.org/2000/svg' version='1.1'><circle cx='4' cy='4' r='"+(n+1)+"'/></svg></p>");
        TagNode p=tree.findElementByName("p",true),svg=tree.findElementByName("svg",true),circle=tree.findElementByName("circle",true);
        return p!=null && svg!=null && circle!=null && svg.getParent()==p && circle.getParent()==svg?1:0;
    }
    public static long control(int n) {
        TagNode p=new HtmlCleaner().clean("<p><span>a</span></p>").findElementByName("p",true);
        TagNode span=p.findElementByName("span",true);return span.getParent()==p && span.getText().toString().equals("a")?1:0;
    }
}
