package providers;
import styleapi.Construction;
import styleapi.PageStyle;
public final class Wide implements PageStyle {
    public Wide() { Construction.log += "W"; }
    public String name() { return "W"; }
}
