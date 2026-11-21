import com.ea.async.Task;
import com.ea.async.instrumentation.Transformer;
import org.objectweb.asm.ClassReader;
import java.util.Base64;

public final class UpgradeProbe {
    public interface AsyncFunction { Task<?> apply(Object value) throws Exception; }
    private static final class Loader extends ClassLoader {
        Class<?> define(byte[] bytes) { return defineClass(null, bytes, 0, bytes.length); }
    }
    public static String observe(String[] args) throws Exception {
        byte[] fixed = Base64.getDecoder().decode(args[0]);
        byte[] transformed = new Transformer().transform(UpgradeProbe.class.getClassLoader(), new ClassReader(fixed));
        AsyncFunction method = (AsyncFunction)new Loader().define(transformed).getDeclaredConstructor().newInstance();
        return String.valueOf(method.apply(Task.fromValue(args[1])).join());
    }
}
