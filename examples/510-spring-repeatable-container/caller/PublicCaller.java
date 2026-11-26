import org.springframework.core.annotation.MergedAnnotations;

import java.lang.annotation.*;
import java.util.*;

public class PublicCaller {
    @Retention(RetentionPolicy.RUNTIME)
    @Repeatable(Tags.class)
    public @interface Tag {
        String value();
    }

    @Retention(RetentionPolicy.RUNTIME)
    public @interface Tags {
        Tag[] value();
    }

    @Retention(RetentionPolicy.RUNTIME)
    public @interface Bundle {
        Tag[] value();
    }

    @Bundle({@Tag("a"), @Tag("b")})
    static class Lookalike {}

    @Tag("a")
    @Tag("b")
    static class Official {}

    @Tag("live")
    @Bundle(@Tag("decoy"))
    static class Mixed {}

    public static String observe(String[] args) {
        Class<?> fixture =
                switch (args[0]) {
                    case "lookalike" -> Lookalike.class;
                    case "official" -> Official.class;
                    default -> Mixed.class;
                };
        var spring =
                MergedAnnotations.from(fixture).stream(Tag.class)
                        .map(a -> a.getString("value"))
                        .sorted()
                        .toList();
        var jdk =
                Arrays.stream(fixture.getDeclaredAnnotationsByType(Tag.class))
                        .map(Tag::value)
                        .toList();
        return spring
                + "/"
                + jdk
                + (fixture == Mixed.class
                        ? "/" + fixture.getAnnotation(Bundle.class).value()[0].value()
                        : "");
    }
}
