import static org.intheloop.controls.Grid.*;
public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("case","positive"),fields("holds",HexClient.boxedValue("7fffffff")),fields());
        row(1, fields("case","nonnull"),fields("holds",HexClient.nullReturns("7ffffff~")),fields());
        row(2, fields("case","minimum"),fields("holds",HexClient.rejectsMinimum("-80000000")),fields());
        row(3, fields("case","order"),fields("holds",HexClient.earlyKey("d==F")),fields());
        row(4, fields("case","sign"),fields("holds",HexClient.dropSign("id=-F")),fields());
        row(5, fields("case","null"),fields("holds",HexClient.nullShape()),fields());
    }
}
