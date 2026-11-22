package springwork;
import static org.intheloop.controls.Grid.*;
public final class Cases {
    static Object[][] trace(int mode) {
        var values = DateEdits.history(mode);
        Object[][] result = new Object[values.length][];
        for (int i = 0; i < values.length; i++) result[i] = values[i].values();
        return result;
    }
    public static void main(String[] args) {
        for (int i = 0; i < 2; i++) row(i,fields("history",i),
            fields("annotated",trace(i == 0 ? 0 : 3),"preservation",trace(i == 0 ? 1 : 2)),
            fields("annotated",DateEdits.annotated(i),"preservation",DateEdits.preservation(i)));
    }
}
