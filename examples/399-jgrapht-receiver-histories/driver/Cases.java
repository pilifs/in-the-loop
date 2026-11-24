import static org.intheloop.controls.Grid.*;
public final class Cases {
    public static void main(String[] args) {
        row(0, fields("call", "registered edge and unregistered source"), fields("holds", GraphHistory.identities(0)), fields());
        row(1, fields("call", "fresh edge and unregistered source"), fields("holds", GraphHistory.identities(1)), fields());
        row(2, fields("call", "null edge and registered endpoints"), fields("holds", GraphHistory.identities(2)), fields());
    }
}
