import java.util.*;
import org.springframework.beans.PropertyAccessorFactory;

public class PublicCaller {
    public static class Child {
        String name;
        Child(String name) { this.name = name; }
        public String getName() { return name; }
        public void setName(String name) { this.name = name; }
    }
    public static class Bean {
        final Map<String, Child> map = Map.of("key5[foo]", new Child("full"), "key5[foo", new Child("prefix"), "plain", new Child("control"));
        public Map<String, Child> getMap() { return map; }
    }
    public static String observe(String[] args) {
        var b = new Bean();
        var accessor = PropertyAccessorFactory.forBeanPropertyAccess(b);
        if (args[0].equals("read")) return (String) accessor.getPropertyValue("map[key5[foo]].name");
        if (args[0].equals("plain")) {
            Object first = accessor.getPropertyValue("map[plain].name");
            accessor.setPropertyValue("map[plain].name","control2");
            return first + " -> " + b.map.get("plain").name;
        }
        accessor.setPropertyValue("map['key5[foo]'].name","changed");
        return b.map.get("key5[foo]").name + "/" + b.map.get("key5[foo").name + "/"
                + accessor.getPropertyValue("map[\"key5[foo]\"].name") + " keys=" + b.map.size();
    }
}
