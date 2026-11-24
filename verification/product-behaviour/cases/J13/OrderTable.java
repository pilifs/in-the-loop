import java.lang.reflect.Field;
import java.util.List;
import java.util.stream.Collectors;
import org.apache.maven.artifact.versioning.ComparableVersion;

public class OrderTable {
    private static Object field(Object owner, String name) {
        try {
            Field f = owner.getClass().getDeclaredField(name);
            f.setAccessible(true);
            return f.get(owner);
        } catch (ReflectiveOperationException e) { throw new AssertionError(e); }
    }
    private static String item(Object value) {
        if (value instanceof List<?> list)
            return "L[" + list.stream().map(OrderTable::item).collect(Collectors.joining(",")) + "]";
        String type = value.getClass().getSimpleName();
        if (!type.equals("IntItem") && !type.equals("StringItem")) throw new AssertionError("unbound item " + type);
        return (type.equals("IntItem") ? "I" : "S") + field(value,"value");
    }
    public static void main(String[] args) {
        for (String[] scope : new String[][]{{"0-alpha","0","x"},{"1-alpha","1-beta"}}) {
            for (String left : scope) for (String right : scope) {
                ComparableVersion l = new ComparableVersion(left), r = new ComparableVersion(right);
                String ls = item(field(l,"items")), rs = item(field(r,"items"));
                int result = l.compareTo(r);
                if (!ls.equals(item(field(l,"items"))) || !rs.equals(item(field(r,"items"))))
                    throw new AssertionError("comparison mutated its parsed operands");
                System.out.println(String.join("\t",left,ls,right,rs,Integer.toString(result)));
            }
        }
    }
}
