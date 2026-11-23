import static org.intheloop.controls.Grid.*;
public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("case","exact"),fields("holds",FloatHistory.exact(Float.intBitsToFloat(0x3f800001),1f)),fields());
        row(1, fields("case","translated"),fields("holds",FloatHistory.translated(Float.intBitsToFloat(0x3f800001),1f)),fields());
        row(2, fields("case","round"),fields("holds",FloatHistory.rounded(Float.intBitsToFloat(0x3f800001),1f)),fields());
        row(3, fields("case","adjacent"),fields("holds",FloatHistory.adjacent(2f,3f)),fields());
    }
}
