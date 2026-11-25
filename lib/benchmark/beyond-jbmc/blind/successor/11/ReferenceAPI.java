import org.jetbrains.annotations.ApiStatus;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;

public final class ReferenceAPI {
    public static long primary(int n) {
        try { return new ApiStatus().getClass() == ApiStatus.class ? 1 : 0; }
        catch (IllegalAccessError expected) { return -1; }
    }
    public static long control(int n) {
        return ApiStatus.Experimental.class.getAnnotation(Retention.class).value() == RetentionPolicy.CLASS ? 1 : 0;
    }
}
