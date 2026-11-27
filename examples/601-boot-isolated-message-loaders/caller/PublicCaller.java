import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicReference;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.context.MessageSourceAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.support.ResourceBundleMessageSource;

public class PublicCaller {
    static String read(ClassLoader loader, String basename) {
        var result = new AtomicReference<String>();
        new ApplicationContextRunner().withClassLoader(loader)
                .withConfiguration(AutoConfigurations.of(MessageSourceAutoConfiguration.class))
                .withPropertyValues("spring.messages.basename=" + basename).run(ctx -> result.set(
                        !ctx.getBeansOfType(ResourceBundleMessageSource.class).isEmpty() + ":"
                        + ctx.getMessage("foo", null, "missing", Locale.UK)));
        return result.get();
    }
    public static String observe(String[] args) throws Exception {
        String basename = "fixture/" + args[0];
        Path root = Files.createTempDirectory("bundles");
        Files.createDirectory(root.resolve("fixture"));
        Files.writeString(root.resolve(basename + ".properties"), "foo=bar\n");
        ClassLoader shared = PublicCaller.class.getClassLoader();
        try (var visible = new URLClassLoader(new URL[] {root.toUri().toURL()}, shared);
             var hidden = new URLClassLoader(new URL[0], shared)) {
            return switch (args[0]) {
                case "intent" -> read(hidden, basename) + "/" + read(visible, basename);
                case "control" -> read(visible, basename) + "/" + read(visible, basename);
                case "challenge" -> read(visible, basename) + "/" + read(hidden, basename);
                default -> throw new IllegalArgumentException(args[0]);
            };
        }
    }
}
