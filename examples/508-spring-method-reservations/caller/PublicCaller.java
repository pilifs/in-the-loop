import org.springframework.aot.generate.*;
import org.springframework.javapoet.ClassName;

import java.util.StringJoiner;

public class PublicCaller {
    static GeneratedClass fresh() {
        var names = new ClassNameGenerator(ClassName.get("example", "Fixture"));
        GenerationContext context =
                new DefaultGenerationContext(names, new InMemoryGeneratedFiles());
        return context.getGeneratedClasses().addForFeature("Probe", type -> {});
    }

    static String request(GeneratedClass type, String... names) {
        var result = new StringJoiner(",");
        for (String name : names) result.add(type.getMethods().add(name, method -> {}).getName());
        return result.toString();
    }

    public static String observe(String[] args) {
        GeneratedClass first = fresh();
        if (args[0].equals("single")) {
            first.reserveMethodNames("apply");
            return request(first, "apply", "test");
        }
        try {
            first.reserveMethodNames("apply", "test");
        } catch (IllegalStateException e) {
            return e.getClass().getSimpleName();
        }
        if (args[0].equals("names")) return request(first, "apply", "test");
        GeneratedClass second = fresh();
        second.reserveMethodNames("apply");
        second.reserveMethodNames("test");
        String[] sequence = {"test", "applyTest", "apply", "test"};
        return request(first, sequence) + " / " + request(second, sequence);
    }
}
