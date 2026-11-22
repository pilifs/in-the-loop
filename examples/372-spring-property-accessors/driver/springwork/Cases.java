package springwork;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        for (int i = 0; i < 3; i++) {
            row(i, new String[]{Accessors.type(i).getSimpleName(), Accessors.method(i),
                                Accessors.type(i+3).getSimpleName(), Accessors.method(i+3)},
                    fields("components", Accessors.name(i), "getters", Accessors.name(i+3)),
                    fields("components", Accessors.components(i), "getters", Accessors.getters(i)));
        }
    }
}
