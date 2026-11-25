import java.io.StringReader;
import com.steadystate.css.parser.CSSOMParser;
import com.steadystate.css.parser.SACParserCSS21;
import org.w3c.css.sac.InputSource;
import org.w3c.dom.css.CSSPrimitiveValue;

public final class ReferenceAPI {
    private static CSSPrimitiveValue parse(String text) throws Exception {
        return (CSSPrimitiveValue) new CSSOMParser(new SACParserCSS21()).parsePropertyValue(new InputSource(new StringReader(text)));
    }
    public static long primary(int n) throws Exception {
        String text = n == 0 ? "17vw" : "17vh";
        CSSPrimitiveValue v = parse(text);
        return v != null && text.equals(v.getCssText()) && v.getPrimitiveType() == CSSPrimitiveValue.CSS_DIMENSION
            && v.getFloatValue(CSSPrimitiveValue.CSS_DIMENSION) == 17 ? 1 : 0;
    }
    public static long control(int n) throws Exception {
        CSSPrimitiveValue px = parse("17px");
        return px.getPrimitiveType() == CSSPrimitiveValue.CSS_PX && px.getFloatValue(CSSPrimitiveValue.CSS_PX) == 17 ? 1 : 0;
    }
}
