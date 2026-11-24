import org.jsoup.Jsoup;
import org.jsoup.nodes.*;
import org.jsoup.parser.Parser;

public final class MarkupHistory {
    private static boolean names(FormElement f,int count,Element b) {
        return f.elements().size()==count && f.elements().get(0).attr("name").equals("a")
            && (count==1 || f.elements().get(1)==b);
    }
    public static boolean form(boolean html) {
        Document d=Jsoup.parse("<form><input name=a></form>");
        FormElement f=(FormElement)d.selectFirst("form");
        if (!names(f,1,null)) return false;
        Element b;
        if (html) {f.append("<input name=b>");b=f.selectFirst("input[name=b]");}
        else b=f.appendElement("input").attr("name","b");
        boolean append=names(f,2,b);
        b.remove();
        return append && names(f,1,null);
    }
    public static boolean reparent() {
        Document d=Jsoup.parse("<form id=f><input name=a></form><form id=g></form>");
        FormElement f=(FormElement)d.selectFirst("#f"),g=(FormElement)d.selectFirst("#g");
        Element a=f.selectFirst("input");
        g.appendChild(a);
        return f.elements().isEmpty() && g.elements().size()==1 && g.elements().get(0)==a;
    }
    public static boolean xml(char interior) {
        boolean allowed=interior=='-' || interior=='.' || interior=='_' || interior>='a' && interior<='z' || interior>='0' && interior<='9';
        if (!allowed) return true;
        String name=new String(new char[]{'a',interior,'b'});
        Document d=Jsoup.parse("<unit/>","",Parser.xmlParser());
        Element unit=d.selectFirst("unit");unit.attr(name,"7");String serialized=unit.outerHtml();
        Element read=Jsoup.parse(serialized,"",Parser.xmlParser()).selectFirst("unit");
        return serialized.contains(name+"=\"7\"") && read.hasAttr(name) && read.attr(name).equals("7");
    }
}
