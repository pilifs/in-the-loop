import com.ea.async.instrumentation.Transformer;
import java.util.Base64;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import org.objectweb.asm.ClassReader;

public final class UpgradeProbe {
    public interface AF { CompletableFuture<?> apply(Object value) throws Exception; }
    private static final class Loader extends ClassLoader {
        Class<?> define(byte[] data) { return defineClass(null, data, 0, data.length); }
    }
    public static String observe(String[] args) throws Exception {
        byte[] input = Base64.getDecoder().decode(args[0]);
        byte[] result = new Transformer().transform(UpgradeProbe.class.getClassLoader(), new ClassReader(input));
        AF method = (AF) new Loader().define(result).getDeclaredConstructor().newInstance();
        CompletableFuture<Object> argument = new CompletableFuture<>();
        boolean ready = Boolean.parseBoolean(args[1]);
        if (ready) argument.complete(args[2]);
        CompletableFuture<?> answer = method.apply(argument);
        boolean finished = answer.isDone();
        if (!ready) argument.complete(args[2]);
        return finished + "/" + answer.get(10, TimeUnit.SECONDS);
    }
}
