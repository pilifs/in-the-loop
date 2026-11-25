import com.mysql.cj.jdbc.MysqlDataSource;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import javax.sql.DataSource;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.datasource.DelegatingDataSource;
import org.springframework.jdbc.support.incrementer.MySQLMaxValueIncrementer;

public class PublicCaller {
    static <T> T monitor(Class<T> type, InvocationHandler calls) {
        return type.cast(Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[]{type}, calls));
    }

    static Object forward(Object target, Method method, Object[] args) throws Throwable {
        try {
            return method.invoke(target, args);
        } catch (InvocationTargetException e) {
            throw e.getCause();
        }
    }

    // All statements run on the original connection. Record what the incrementer actually
    // reads, then inject one failure at the requested transaction boundary.
    static class Reservations extends DelegatingDataSource {
        final String mode;
        final List<Long> maxima = new ArrayList<>();
        String fault = "none";

        Reservations(DataSource db, String mode) {
            super(db);
            this.mode = mode;
        }

        Statement trace(Statement statement) {
            return monitor(Statement.class, (proxy, method, args) -> {
                Object result = forward(statement, method, args);
                if (!method.getName().equals("executeQuery")
                        || !"select last_insert_id()".equalsIgnoreCase((String) args[0])) return result;
                ResultSet rows = (ResultSet) result;
                return monitor(ResultSet.class, (p, read, columns) -> {
                    Object value = forward(rows, read, columns);
                    if (read.getName().equals("getLong") && Integer.valueOf(1).equals(columns[0])) {
                        maxima.add((Long) value);
                    }
                    return value;
                });
            });
        }

        @Override
        public Connection getConnection() throws SQLException {
            Connection physical = super.getConnection();
            if (!physical.getAutoCommit()) {
                physical.close();
                throw new SQLException("the reservation fixture requires initial auto-commit");
            }
            return monitor(Connection.class, new InvocationHandler() {
                boolean committed;

                public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
                    String op = method.getName();
                    if (op.equals("commit") && mode.equals("rollback") && fault.equals("none")) {
                        physical.rollback();
                        fault = "rollback";
                        throw new SQLException("fixture rolled back the first reservation at commit");
                    }
                    if (op.equals("setAutoCommit") && (Boolean) args[0] && committed
                            && mode.equals("restore") && fault.equals("none")) {
                        fault = "restore";
                        throw new SQLException("fixture failed auto-commit restoration after commit");
                    }
                    Object result = forward(physical, method, args);
                    if (op.equals("commit")) committed = true;
                    if (op.equals("createStatement")) return trace((Statement) result);
                    return result;
                }
            });
        }
    }

    static String readback(DataSource db) throws SQLException {
        // MysqlDataSource is unpooled. Every observation starts a new physical connection.
        try (Connection c = db.getConnection(); Statement s = c.createStatement()) {
            long seq;
            try (ResultSet rows = s.executeQuery("select seq from myseq")) {
                if (!rows.next()) throw new SQLException("empty sequence table");
                seq = rows.getLong(1);
                if (rows.next()) throw new SQLException("multiple sequence rows");
            }
            List<Long> inserted = new ArrayList<>();
            try (ResultSet rows = s.executeQuery("select id from issued order by id")) {
                while (rows.next()) inserted.add(rows.getLong(1));
            }
            return seq + "/" + inserted;
        }
    }

    static String insert(DataSource db, long id) throws SQLException {
        try (Connection c = db.getConnection(); PreparedStatement s = c.prepareStatement("insert into issued values (?)")) {
            c.setAutoCommit(false);
            s.setLong(1, id);
            try {
                s.executeUpdate();
                c.commit();
                return "inserted";
            } catch (SQLException e) {
                c.rollback();
                if (e.getErrorCode() == 1062 && "23000".equals(e.getSQLState())) return "duplicate(1062,23000)";
                throw e;
            }
        }
    }

    static String history(DataSource db, String mode) throws SQLException {
        Reservations reservations = new Reservations(db, mode);
        MySQLMaxValueIncrementer allocator = new MySQLMaxValueIncrementer(reservations, "myseq", "seq");
        allocator.setUseNewConnection(true);
        allocator.setCacheSize(2);
        allocator.afterPropertiesSet();
        String initial = readback(db);
        String first = "none";
        if (!mode.equals("normal")) {
            try {
                long id = allocator.nextLongValue();
                first = "returned:" + id + ":" + insert(db, id);
            } catch (DataAccessResourceFailureException e) {
                first = e.getClass().getSimpleName();
            }
        }
        String afterFirst = readback(db);
        List<String> steps = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            long id = allocator.nextLongValue();
            steps.add(id + ":" + insert(db, id) + ":" + readback(db));
        }
        return "initial=" + initial + " first=" + first + " afterFirst=" + afterFirst + " steps=" + steps
                + " reservations=" + reservations.maxima + " fault=" + reservations.fault;
    }

    public static String observe(String[] args) throws SQLException {
        String mode = args[0];
        if (!List.of("rollback", "normal", "restore").contains(mode)) throw new IllegalArgumentException(mode);
        MysqlDataSource db = new MysqlDataSource();
        db.setURL("jdbc:mysql://127.0.0.1:" + System.getenv("PUBLIC_COMPARISON_MYSQL_PORT")
                + "/comparison?sslMode=REQUIRED&connectTimeout=5000&socketTimeout=10000");
        db.setUser("caller");
        db.setPassword(System.getenv("PUBLIC_COMPARISON_MYSQL_PASSWORD"));
        try (Connection c = db.getConnection(); Statement s = c.createStatement()) {
            s.execute("create table myseq(seq bigint not null) engine=InnoDB");
            s.execute("create table issued(id bigint primary key) engine=InnoDB");
            try {
                s.executeUpdate("insert into myseq values (98)");
                return history(db, mode);
            } finally {
                s.execute("drop table issued, myseq");
            }
        }
    }
}
