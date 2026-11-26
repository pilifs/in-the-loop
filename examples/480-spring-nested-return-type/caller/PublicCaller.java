import java.lang.reflect.*;
import java.util.*;
import java.util.stream.Collectors;
import org.springframework.core.GenericTypeResolver;

public class PublicCaller {
    interface Source<T> { default T get() { return null; } }
    static class Middle<P> implements Source<Collection<P>> {}
    static class Text extends Middle<Optional<String>> { public Collection<Optional<String>> get() { return List.of(); } }
    static class Strings extends Middle<Optional<String>> {}
    static class Longs extends Middle<Optional<Long>> {}
    static class Direct implements Source<String> {}

    static String signature(Type t) {
        if (t instanceof ParameterizedType p)
            return signature(p.getRawType()) + Arrays.stream(p.getActualTypeArguments()).map(PublicCaller::signature)
                    .collect(Collectors.joining(",", "<", ">"));
        return t instanceof Class<?> c ? c.getSimpleName() : t.getTypeName();
    }
    public static String observe(String[] args) throws Exception {
        Type t = Source.class.getMethod("get").getGenericReturnType();
        if (args[0].equals("direct")) return signature(GenericTypeResolver.resolveType(t, Direct.class));
        if (args[0].equals("siblings")) return signature(GenericTypeResolver.resolveType(t, Longs.class))
                + " / " + signature(GenericTypeResolver.resolveType(t, Strings.class));
        Type resolved = GenericTypeResolver.resolveType(t, Text.class);
        Type actual = Arrays.stream(Text.class.getDeclaredMethods()).filter(m -> m.getName().equals("get") && !m.isBridge())
                .findFirst().orElseThrow().getGenericReturnType();
        return signature(resolved) + " equal=" + actual.equals(resolved);
    }
}
