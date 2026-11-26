import io.r2dbc.spi.ConnectionFactories;
import java.util.Locale;
import org.springframework.dao.InvalidDataAccessApiUsageException;
import org.springframework.r2dbc.core.*;

public class PublicCaller {
    public static class PersonBean {
        private String firstName;
        private int age;
        public void setFirstName(String s) { firstName = s; }
        public String getFirstName() { return firstName; }
        public void setAge(int n) { age = n; }
        public int getAge() { return age; }
    }
    public record Person(String firstName, int age) {
        public String toString() { return "Person(" + firstName + "," + age + ")"; }
    }
    public static class Label {
        private String name;
        public Label(String name) { this.name = name.toUpperCase(Locale.ROOT); }
        public void setName(String name) { this.name = name; }
        public String getName() { return name; }
    }

    static boolean present(String name) {
        try { Class.forName("org.springframework.r2dbc.core." + name); return true; }
        catch (ClassNotFoundException e) { return false; }
    }

    public static String observe(String[] args) {
        var client = DatabaseClient.create(ConnectionFactories.get("r2dbc:h2:mem:///mapper"));
        var query = client.sql("SELECT 'Ada' AS first_name, 37 AS age");
        if (args[0].equals("lambda")) return "rows=" + query.map((row, meta) ->
                new Person(row.get("first_name",String.class),row.get("age",Integer.class))).all().collectList().block();
        boolean bean = present("BeanPropertyRowMapper");
        boolean record = present("DataClassRowMapper");
        if (!bean || !record) return "bean=" + (bean ? "present" : "absent") + " record=" + (record ? "present" : "absent");
        if (args[0].equals("map")) {
            var b = query.map(new BeanPropertyRowMapper<>(PersonBean.class)).one().block();
            var p = query.map(new DataClassRowMapper<>(Person.class)).one().block();
            return "bean=" + b.getClass().getSimpleName() + "(" + b.getFirstName() + "," + b.getAge() + ") record=" + p;
        }
        var name = client.sql("SELECT 'Ada' AS name");
        var mapper = new DataClassRowMapper<>(Label.class);
        String normal = name.map(mapper).one().block().getName();
        mapper.setCheckFullyPopulated(true);
        try { return "default=" + normal + " strict=" + name.map(mapper).one().block().getName(); }
        catch (InvalidDataAccessApiUsageException e) { return "default=" + normal + " strict=" + e.getClass().getSimpleName(); }
    }
}
