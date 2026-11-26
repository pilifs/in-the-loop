import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

public class PublicCaller {
    public record Order(long id, String item) {}

    public static class Fixed {
        final long id;
        final String item;

        public Fixed(long id, String item) {
            this.id = id;
            this.item = item;
        }

        public long getId() {
            return id;
        }
    }

    public static class Mutable {
        private long id;
        private String note;
        int calls;

        public Mutable(long id) {
            this.id = id;
        }

        public void setId(long id) {
            this.id = id;
            calls++;
        }

        public void setNote(String note) {
            this.note = note;
        }

        public String getNote() {
            return note;
        }
    }

    static String probe(JdbcClient db, int decoy) {
        var result =
                db.sql("SELECT 1 AS id, 'book' AS item, " + decoy + " AS id, 'packed' AS note")
                        .query(Mutable.class)
                        .single();
        return result.id + ":" + result.calls + ":" + result.getNote();
    }

    public static String observe(String[] args) {
        var source = new DriverManagerDataSource("jdbc:h2:mem:labels", "sa", "");
        var db = JdbcClient.create(source);
        if (args[0].equals("decoy")) return probe(db, 100) + " / " + probe(db, 200);
        String sql =
                "SELECT 1 AS id, 'book' AS item"
                        + (args[0].equals("duplicate") ? ", 100 AS id" : "");
        long first = db.sql(sql).query((r, i) -> r.getLong(1)).single();
        String record;
        try {
            Order order = db.sql(sql).query(Order.class).single();
            record = order.id() + ":" + order.item();
        } catch (IllegalStateException e) {
            record = e.getClass().getSimpleName();
        }
        Fixed obj = db.sql(sql).query(Fixed.class).single();
        return first + "/" + record + "/" + obj.getId() + ":" + obj.item;
    }
}
