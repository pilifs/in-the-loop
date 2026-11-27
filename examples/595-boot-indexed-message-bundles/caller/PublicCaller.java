import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicReference;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.context.MessageSourceAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

public class PublicCaller {
    public static String observe(String[] args) throws Exception {
        Path root = Files.createTempDirectory("bundles");
        Path dir = Files.createDirectories(root.resolve("test"));
        boolean comma = args[0].equals("challenge");
        if (comma) Files.writeString(dir.resolve("a,b.properties"), "punct=literal\n");
        else {
            Files.writeString(dir.resolve("messages.properties"), "foo=bar\n");
            Files.writeString(dir.resolve("messages2.properties"), "foo-foo=bar-bar\n");
        }
        String[] props = args[0].equals("control")
                ? new String[] {"spring.messages.basename=test/messages,test/messages2"}
                : comma ? new String[] {"spring.messages.basename[0]=test/a,b"}
                : new String[] {"spring.messages.basename[0]=test/messages", "spring.messages.basename[1]=test/messages2"};
        try (var loader = new URLClassLoader(new URL[] {root.toUri().toURL()}, PublicCaller.class.getClassLoader())) {
            var answer = new AtomicReference<String>();
            new ApplicationContextRunner().withClassLoader(loader)
                    .withConfiguration(AutoConfigurations.of(MessageSourceAutoConfiguration.class))
                    .withPropertyValues(props).run(ctx -> answer.set(comma ? ctx.getMessage("punct", null, "MISS", Locale.UK)
                            : ctx.getMessage("foo", null, "MISS", Locale.UK) + "/" + ctx.getMessage("foo-foo", null, "MISS", Locale.UK)));
            return answer.get();
        }
    }
}
