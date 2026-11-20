package providers;
import styleapi.Construction;
import styleapi.PageStyle;
public final class Compact implements PageStyle {
    public Compact() { Construction.log += "C"; }
    public String name() { return "C"; }
}
