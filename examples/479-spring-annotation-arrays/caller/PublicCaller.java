import java.lang.annotation.*;
import java.util.*;
import org.springframework.core.annotation.MergedAnnotation;

public class PublicCaller {
    @Retention(RetentionPolicy.RUNTIME)
    public @interface Options { int[] codes(); String[] names(); }
    @Options(codes={7}, names={"east"}) static class Annotated {}

    public static String observe(String[] args) {
        var mapped = MergedAnnotation.of(Options.class, Map.of("codes", 7, "names", "east"));
        try {
            if (args[0].equals("codes")) {
                int[] codes = mapped.getIntArray("codes");
                return codes.getClass().getTypeName() + " " + Arrays.toString(codes);
            }
            if (args[0].equals("ordinary")) {
                String[] names = mapped.getStringArray("names");
                int[] codes = MergedAnnotation.of(Options.class, Map.of("codes", new int[]{7,9})).getIntArray("codes");
                return "String[] " + Arrays.toString(names) + " int[] " + Arrays.toString(codes);
            }
            Options a = mapped.synthesize(), b = Annotated.class.getAnnotation(Options.class);
            return "codes=" + Arrays.equals(a.codes(), b.codes()) + " names=" + Arrays.equals(a.names(), b.names());
        } catch (IllegalStateException e) {
            return e.getClass().getSimpleName();
        }
    }
}
