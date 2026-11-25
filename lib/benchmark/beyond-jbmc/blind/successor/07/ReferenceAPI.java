import javax.annotation.Resource;
import javax.annotation.Resources;

public final class ReferenceAPI {
    @Resources({@Resource(name = "left"), @Resource(name = "right")})
    public static final class Tagged {}
    public static final class Empty {}
    private static Class<?> target(int n) {
        return n == 0 ? Tagged.class : Empty.class;
    }
    private static long observe(Resource[] values) {
        if (values.length == 0) return 0;
        return values.length == 2 && values[0].name().equals("left") && values[1].name().equals("right") ? 2 : -1;
    }
    public static long primary(int n) throws Exception {
        return observe(target(n).getAnnotationsByType(Resource.class));
    }
    public static long control(int n) throws Exception {
        Resources r = target(n).getAnnotation(Resources.class);
        return r == null ? 0 : observe(r.value());
    }
}
