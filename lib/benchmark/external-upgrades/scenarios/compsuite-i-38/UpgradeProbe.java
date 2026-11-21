import com.esotericsoftware.reflectasm.MethodAccess;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

public final class UpgradeProbe {
    public static String observe(String[] args) {
        boolean map = "map".equals(args[0]);
        MethodAccess access = MethodAccess.get(map ? ConcurrentMap.class : Object.class);
        if (!map) return "methods:" + access.getMethodNames().length;
        ConcurrentMap<String, String> values = new ConcurrentHashMap<>();
        values.put("first", "one");
        values.put("second", "two");
        Object previous = access.invoke(values, "replace", "first", "updated");
        return previous + "/" + access.invoke(values, "size");
    }
}
